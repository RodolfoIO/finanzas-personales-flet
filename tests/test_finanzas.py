from pathlib import Path

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
