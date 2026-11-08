from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def _number(value: str) -> float:
    clean = (value or "").strip().replace("Q", "").replace("$", "").replace(" ", "")
    if not clean:
        return 0.0
    if "," in clean and "." not in clean:
        clean = clean.replace(",", ".")
    else:
        clean = clean.replace(",", "")
    try:
        return float(clean)
    except ValueError:
        return 0.0


def _date(value: str) -> str | None:
    value = (value or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _hash(account_id: str, transaction_date: str, description: str, amount: float) -> str:
    raw = f"{account_id}|{transaction_date}|{description.strip()}|{amount:.2f}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_file(path: str | Path, account_id: str, store: Any) -> list[dict[str, Any]]:
    path = Path(path)
    if path.suffix.lower() == ".txt":
        return _parse_gt(path, account_id, store)
    return _parse_csv(path, account_id, store)


def _parse_csv(path: Path, account_id: str, store: Any) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        rows = list(csv.reader(handle))
    header_index = next((i for i, row in enumerate(rows) if row and row[0].strip().lower().startswith("fecha") and len(row) >= 6), -1)
    if header_index < 0:
        header_index = next((i for i, row in enumerate(rows) if any(cell.strip().lower() == "date" for cell in row) and any(cell.strip().lower() in ("local", "dollars") for cell in row)), -1)
    if header_index < 0:
        return []
    headers = [cell.strip().lower() for cell in rows[header_index]]
    is_account = len(headers) >= 6 and any("descrip" in cell or "transacci" in cell for cell in headers)
    result: list[dict[str, Any]] = []
    for row in rows[header_index + 1 :]:
        if not row:
            continue
        transaction_date = _date(row[0] if row else "")
        if not transaction_date:
            continue
        if is_account:
            description = row[3].strip() if len(row) > 3 else "Movimiento bancario"
            debit = _number(row[4] if len(row) > 4 else "")
            credit = _number(row[5] if len(row) > 5 else "")
            amount = debit - credit
        else:
            description = row[1].strip() if len(row) > 1 else "Consumo tarjeta"
            amount = _number(row[2] if len(row) > 2 else "")
            if amount == 0 and len(row) > 3:
                amount = _number(row[3])
        if amount == 0:
            continue
        result.append(_row(account_id, transaction_date, description, amount, path.name, store))
    return result


def _parse_gt(path: Path, account_id: str, store: Any) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        lines = [line.rstrip("\n") for line in handle]
    header_index = next((i for i, line in enumerate(lines) if line.startswith("Fecha\t")), -1)
    if header_index < 0:
        return []
    result: list[dict[str, Any]] = []
    for line in lines[header_index + 1 :]:
        cells = line.split("\t")
        transaction_date = _date(cells[0] if cells else "")
        if not transaction_date:
            continue
        description = " ".join(cell.strip() for cell in cells[1:3] if cell.strip()) or "Movimiento G&T"
        debit = _number(cells[3] if len(cells) > 3 else "")
        credit = _number(cells[4] if len(cells) > 4 else "")
        amount = debit - credit
        if amount:
            result.append(_row(account_id, transaction_date, description, amount, path.name, store))
    return result


def _row(account_id: str, transaction_date: str, description: str, amount: float, source: str, store: Any) -> dict[str, Any]:
    clean_description = re.sub(r"\s+", " ", description).strip()
    suggestion = store.suggest_classification(clean_description) if hasattr(store, "suggest_classification") else None
    return {"account_id": account_id, "category_id": suggestion["category_id"] if suggestion else (store.guess_category_id(clean_description) if amount > 0 else None), "subcategory_id": suggestion["subcategory_id"] if suggestion else None, "transaction_date": transaction_date, "description": clean_description, "amount": amount, "transaction_type": "expense" if amount > 0 else "income", "source": source, "source_hash": _hash(account_id, transaction_date, description, amount)}


def import_file(path: str | Path, account_id: str, store: Any) -> tuple[int, int]:
    rows = parse_file(path, account_id, store)
    imported = sum(1 for row in rows if store.add_transaction(row))
    return imported, len(rows) - imported
