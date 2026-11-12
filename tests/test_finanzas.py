from pathlib import Path

import pytest

from importers import parse_file
from migration import migrate_existing_data
from store import DataStore


def test_import_bac_account(tmp_path: Path):
    source = tmp_path / "bac.csv"
    source.write_text(
        "Fecha de Transacción,Referencia de Transacción,Código de Transacción,Descripción de Transacción,Débito de Transacción,Crédito de Transacción,Balance de Transacción\n"
        "06/10/2026,1,DB,COMPRA SUPERMERCADO,125.50,0,0\n"
        "07/10/2026,2,MC,NOMINA,0,1000,0\n",
        encoding="utf-8",
    )
    store = DataStore(str(tmp_path / "db.sqlite3"))
    rows = parse_file(source, store.accounts()[0]["id"], store)
    assert len(rows) == 2
    assert rows[0]["amount"] == 125.50
    assert rows[1]["amount"] == -1000
    assert rows[0]["category_id"] is not None
    store.close()


def test_duplicate_transactions_are_ignored(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"))
    account_id = store.accounts()[0]["id"]
    row = {"account_id": account_id, "transaction_date": "2026-10-01", "description": "Compra", "amount": 10}
    assert store.add_transaction(row) is True
    assert store.add_transaction(row) is False
    assert len(store.transactions("2026-10")) == 1
    store.close()


def test_multiple_named_accounts_and_cards_are_supported(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"))
    store.add_account("Cuenta de ahorro", "BAC", "cuenta")
    store.add_account("Tarjeta Platinum", "BAC", "tarjeta")
    store.add_account("Tarjeta de viajes", "G&T", "tarjeta")

    names = {row["name"] for row in store.accounts()}
    assert {"Cuenta de ahorro", "Tarjeta Platinum", "Tarjeta de viajes"} <= names
    store.close()


def test_deleting_account_removes_its_movements_as_origin_or_destination(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    store.remote.base_url = ""
    store.remote.key = ""
    origin = store.accounts()[0]["id"]
    destination = store.add_account("Cuenta destino", "BAC", "cuenta")["id"]
    other = store.add_account("Cuenta intacta", "G&T", "cuenta")["id"]

    store.add_transaction({"account_id": origin, "transaction_date": "2026-10-01", "description": "Gasto", "amount": 25})
    store.add_transfer(origin, destination, 100, "2026-10-02", "Transferencia saliente")
    store.add_transfer(other, origin, 50, "2026-10-03", "Transferencia entrante")
    store.add_transaction({"account_id": other, "transaction_date": "2026-10-04", "description": "Conservar", "amount": 10})

    assert store.account_transaction_count(origin) == 3
    assert store.delete_account(origin) == 3
    assert not any(account["id"] == origin for account in store.accounts())
    assert len(store.transactions()) == 1
    assert store.transactions()[0]["description"] == "Conservar"
    store.close()


def test_deleting_last_account_is_allowed(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    store.remote.base_url = ""
    store.remote.key = ""
    account_id = store.accounts()[0]["id"]

    assert store.delete_account(account_id) == 0
    assert store.accounts() == []
    store.close()


def test_delete_account_keeps_local_data_when_remote_delete_fails(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    account_id = store.accounts()[0]["id"]

    class FailingRemote:
        enabled = True
        last_error = "Error remoto simulado"

        def delete(self, table: str, query: str) -> bool:
            return False

    store.remote = FailingRemote()
    with pytest.raises(RuntimeError, match="Error remoto simulado"):
        store.delete_account(account_id)
    assert any(account["id"] == account_id for account in store.accounts())
    store.close()


def test_existing_files_migrate_idempotently(tmp_path: Path):
    source = tmp_path / "source"
    (source / "cuenta BAC").mkdir(parents=True)
    (source / "tarjeta BAC").mkdir()
    (source / "cuenta G&T").mkdir()
    (source / "cuenta BAC" / "enero.csv").write_text(
        "Fecha de Transacción,Referencia de Transacción,Código de Transacción,Descripción de Transacción,Débito de Transacción,Crédito de Transacción,Balance de Transacción\n"
        "06/10/2026,1,DB,COMPRA SUPERMERCADO,125.50,0,0\n",
        encoding="utf-8",
    )
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)

    first = migrate_existing_data(source, store)
    second = migrate_existing_data(source, store)

    assert first["imported"] == 1
    assert second["imported"] == 0
    assert len(store.transactions()) == 1
    assert store.find_account("Cuenta BAC", "BAC", "cuenta") is not None
    store.close()


def test_subcategories_belong_to_categories_and_classify_transactions(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    account_id = store.accounts()[0]["id"]
    category_id = next(category["id"] for category in store.categories() if category["name"] == "Alimentación")
    subcategory = store.add_subcategory(category_id, "Supermercado")

    assert store.subcategories(category_id)[0]["name"] == "Supermercado"
    assert store.add_transaction({
        "account_id": account_id,
        "category_id": category_id,
        "subcategory_id": subcategory["id"],
        "transaction_date": "2026-10-01",
        "description": "Compra semanal",
        "amount": 125,
    }) is True
    row = store.transactions("2026-10")[0]
    assert row["category_name"] == "Alimentación"
    assert row["subcategory_name"] == "Supermercado"
    store.close()


def test_deleting_subcategory_keeps_transaction_category(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    account_id = store.accounts()[0]["id"]
    category_id = store.categories()[0]["id"]
    subcategory = store.add_subcategory(category_id, "Temporal")
    store.add_transaction({
        "account_id": account_id,
        "category_id": category_id,
        "subcategory_id": subcategory["id"],
        "transaction_date": "2026-10-02",
        "description": "Compra",
        "amount": 10,
    })

    store.delete_subcategory(subcategory["id"])
    row = store.transactions("2026-10")[0]
    assert row["category_id"] == category_id
    assert row["subcategory_id"] is None
    store.close()


def test_reuses_previous_classification_for_repeated_description(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    account_id = store.accounts()[0]["id"]
    category_id = next(category["id"] for category in store.categories() if category["name"] == "Transporte")
    subcategory = store.add_subcategory(category_id, "Parqueo")
    base = {"account_id": account_id, "category_id": category_id, "subcategory_id": subcategory["id"], "description": "PARQUEO PORTALES COMPASS", "amount": 10}
    assert store.add_transaction({**base, "transaction_date": "2026-10-01"}) is True

    suggestion = store.suggest_classification("Parqueo Portales Compass")
    assert suggestion == {"category_id": category_id, "subcategory_id": subcategory["id"]}
    assert store.add_transaction({"account_id": account_id, "transaction_date": "2026-10-02", "description": "Parqueo Portales Compass", "amount": 12}) is True
    repeated = store.transactions("2026-10")[0]
    assert repeated["category_id"] == category_id
    assert repeated["subcategory_id"] == subcategory["id"]
    store.close()


def test_transfer_is_single_uncategorized_record_and_excluded_from_summary(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    origin = store.accounts()[0]["id"]
    destination = store.add_account("Cuenta destino", "BAC", "cuenta")["id"]

    assert store.add_transfer(origin, destination, 250, "2026-10-03", "Fondo de ahorro") is True
    row = store.transactions("2026-10")[0]
    assert row["transaction_type"] == "transfer"
    assert row["destination_account_id"] == destination
    assert row["category_id"] is None
    assert row["subcategory_id"] is None
    assert store.summary("2026-10") == {"expenses": 0, "income": 0, "balance": 0, "by_category": {}, "count": 0}
    assert store.account_balance(origin) == -250
    assert store.account_balance(destination) == 250
    store.close()


def test_card_payment_reduces_debt_and_bridge_transfer_balances(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    bank_a = store.accounts()[0]["id"]
    bank_b = store.add_account("Cuenta puente", "BAC", "cuenta")["id"]
    card = store.add_account("Visa", "BAC", "tarjeta")["id"]

    assert store.add_transaction({"account_id": card, "transaction_date": "2026-10-01", "description": "Compra", "amount": 500, "transaction_type": "expense"})
    assert store.add_transfer(bank_a, bank_b, 200, "2026-10-02", "Fondo para pago")
    assert store.add_transfer(bank_b, card, 200, "2026-10-03", "Pago de tarjeta Visa")

    assert store.account_balance(card) == 300
    assert store.account_balance(bank_a) == -200
    assert store.account_balance(bank_b) == 0
    assert store.summary("2026-10")["expenses"] == 500
    assert store.summary("2026-10")["count"] == 1
    store.close()


def test_card_payment_credit_is_pending_and_not_income(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    bank = store.accounts()[0]["id"]
    card = store.add_account("Visa", "BAC", "tarjeta")["id"]
    source = tmp_path / "card.csv"
    source.write_text(
        "Fecha de Transacción,Referencia de Transacción,Código de Transacción,Descripción de Transacción,Débito de Transacción,Crédito de Transacción,Balance de Transacción\n"
        "06/10/2026,1,DB,COMPRA SUPERMERCADO,500,0,0\n"
        "07/10/2026,2,CR,PAGO TARJETA VISA,0,200,0\n",
        encoding="utf-8",
    )

    rows = parse_file(source, card, store)
    assert rows[1]["transaction_type"] == "card_payment_pending"
    assert store.add_transaction(rows[0]) is True
    assert store.add_transaction(rows[1]) is True
    assert store.summary("2026-10")["income"] == 0
    assert store.summary("2026-10")["expenses"] == 500
    assert store.card_payment_candidates(card)[0]["description"] == "PAGO TARJETA VISA"
    assert store.account_balance(card) == 500

    store.convert_card_payment(store.card_payment_candidates(card)[0]["id"], bank)

    assert store.summary("2026-10")["income"] == 0
    assert store.summary("2026-10")["expenses"] == 500
    assert store.account_balance(bank) == -200
    assert store.account_balance(card) == 300
    assert store.transactions("2026-10")[0]["transaction_type"] == "transfer"
    store.close()


def test_card_payment_reconciles_bank_debit_in_either_import_order(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    bank = store.accounts()[0]["id"]
    card = store.add_account("Visa", "BAC", "tarjeta")["id"]
    assert store.add_transaction({"account_id": card, "transaction_date": "2026-10-01", "description": "Compra", "amount": 500})
    pending = {"account_id": card, "transaction_date": "2026-10-03", "description": "PAGO TARJETA VISA", "amount": -200, "transaction_type": "card_payment_pending", "source_hash": "card-payment-1"}
    assert store.add_transaction(pending)
    payment_id = store.card_payment_candidates(card)[0]["id"]
    store.convert_card_payment(payment_id, bank)

    assert store.add_transaction({"account_id": bank, "transaction_date": "2026-10-03", "description": "PAGO TARJETA VISA", "amount": 200}) is False
    assert store.summary("2026-10")["expenses"] == 500

    other_bank = store.add_account("Cuenta 2", "BAC", "cuenta")["id"]
    other_card = store.add_account("Mastercard", "BAC", "tarjeta")["id"]
    assert store.add_transaction({"account_id": other_card, "transaction_date": "2026-10-05", "description": "Compra", "amount": 300})
    assert store.add_transaction({"account_id": other_bank, "transaction_date": "2026-10-07", "description": "PAGO TARJETA MASTERCARD", "amount": 100})
    assert store.add_transaction({**pending, "account_id": other_card, "transaction_date": "2026-10-07", "description": "PAGO TARJETA MASTERCARD", "amount": -100, "source_hash": "card-payment-2"})
    other_payment_id = store.card_payment_candidates(other_card)[0]["id"]
    store.convert_card_payment(other_payment_id, other_bank)

    assert not any(row["account_id"] == other_bank and row["transaction_type"] == "expense" for row in store.transactions())
    assert store.account_balance(other_bank) == -100
    assert store.account_balance(other_card) == 200
    store.close()


def test_historical_card_income_can_be_converted_to_payment(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    bank = store.accounts()[0]["id"]
    card = store.add_account("Visa", "BAC", "tarjeta")["id"]
    assert store.add_transaction({"account_id": card, "transaction_date": "2026-10-01", "description": "Compra", "amount": 400})
    assert store.add_transaction({"account_id": card, "transaction_date": "2026-10-02", "description": "PAGO TARJETA VISA", "amount": -150, "transaction_type": "income"})
    payment = store.card_payment_candidates(card)[0]
    store.convert_card_payment(payment["id"], bank)

    row = next(item for item in store.transactions() if item["description"] == "PAGO TARJETA VISA")
    assert row["transaction_type"] == "transfer"
    assert store.summary("2026-10")["income"] == 0
    assert store.account_balance(card) == 250
    store.close()


def test_transfer_validation_and_destination_sensitive_deduplication(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    origin = store.accounts()[0]["id"]
    destination = store.add_account("Destino", "BAC", "cuenta")["id"]

    with pytest.raises(ValueError):
        store.add_transfer(origin, None, 10, "2026-10-01")
    with pytest.raises(ValueError):
        store.add_transfer(origin, origin, 10, "2026-10-01")
    with pytest.raises(ValueError):
        store.add_transfer(origin, destination, 10, "2026-10-01", category_id="category")

    assert store.add_transfer(origin, destination, 10, "2026-10-01", "A") is True
    other_destination = store.add_account("Otro destino", "BAC", "cuenta")["id"]
    assert store.add_transfer(origin, other_destination, 10, "2026-10-01", "A") is True
    store.close()


def test_transaction_type_can_be_changed_and_normalizes_amount_sign(tmp_path: Path):
    store = DataStore(str(tmp_path / "db.sqlite3"), sync_remote=False)
    account_id = store.accounts()[0]["id"]
    assert store.add_transaction({"account_id": account_id, "transaction_date": "2026-10-01", "description": "Movimiento", "amount": 75, "transaction_type": "expense"})

    transaction_id = store.transactions()[0]["id"]
    store.update_transaction_type(transaction_id, "income")
    row = store.transactions()[0]
    assert row["transaction_type"] == "income"
    assert row["amount"] == -75
    store.close()
