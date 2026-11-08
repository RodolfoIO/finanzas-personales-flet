from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from importers import parse_file


SOURCE_GROUPS = (
    ("cuenta BAC", "Cuenta BAC", "BAC", "cuenta", "*.csv"),
    ("tarjeta BAC", "Tarjeta BAC", "BAC", "tarjeta", "*.csv"),
    ("cuenta G&T", "Cuenta G&T", "G&T", "cuenta", "*.txt"),
)


def _account_id(name: str, institution: str, account_type: str) -> str:
    """ID estable para que repetir la migración no cree otra cuenta."""
    key = f"pulso-financiero:{institution.lower()}:{account_type}:{name.lower()}"
    return str(uuid5(NAMESPACE_URL, key))


def migrate_existing_data(source_root: str | Path, store: Any) -> dict[str, Any]:
    """Importa los estados históricos del archivo financiero de forma idempotente."""
    root = Path(source_root).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de datos: {root}")

    report: dict[str, Any] = {"accounts": [], "files": 0, "imported": 0, "skipped": 0}
    for folder_name, account_name, institution, account_type, pattern in SOURCE_GROUPS:
        folder = root / folder_name
        if not folder.is_dir():
            continue
        account = store.find_account(account_name, institution, account_type)
        if account is None:
            account = store.add_account(
                account_name,
                institution,
                account_type,
                account_id=_account_id(account_name, institution, account_type),
            )
        account_report = {"name": account_name, "type": account_type, "files": 0, "imported": 0, "skipped": 0}
        for path in sorted(folder.glob(pattern)):
            rows = parse_file(path, account["id"], store)
            imported = sum(1 for row in rows if store.add_transaction(row))
            account_report["files"] += 1
            account_report["imported"] += imported
            account_report["skipped"] += len(rows) - imported
        report["accounts"].append(account_report)
        report["files"] += account_report["files"]
        report["imported"] += account_report["imported"]
        report["skipped"] += account_report["skipped"]
    return report
