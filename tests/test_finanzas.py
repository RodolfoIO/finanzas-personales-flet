from pathlib import Path

from importers import parse_file
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
