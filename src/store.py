from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_CATEGORIES = [
    ("Vivienda", "#6C63FF", 3500.0),
    ("Alimentación", "#F59E0B", 2500.0),
    ("Transporte", "#0EA5E9", 1200.0),
    ("Salud", "#10B981", 1000.0),
    ("Servicios", "#8B5CF6", 1800.0),
    ("Suscripciones", "#EC4899", 600.0),
    ("Compras", "#F97316", 1800.0),
    ("Entretenimiento", "#14B8A6", 800.0),
    ("Deudas y pagos", "#EF4444", 2500.0),
    ("Otros", "#64748B", 1000.0),
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, color TEXT NOT NULL DEFAULT '#64748B',
    monthly_budget REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, institution TEXT NOT NULL DEFAULT '',
    account_type TEXT NOT NULL DEFAULT 'cuenta', currency TEXT NOT NULL DEFAULT 'GTQ',
    current_balance REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id), category_id TEXT REFERENCES categories(id),
    transaction_date TEXT NOT NULL, description TEXT NOT NULL, amount REAL NOT NULL,
    transaction_type TEXT NOT NULL DEFAULT 'expense', source TEXT NOT NULL DEFAULT 'manual',
    source_hash TEXT UNIQUE, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class SupabaseClient:
    """Cliente REST mínimo para evitar depender de un SDK generado."""

    def __init__(self) -> None:
        url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
        key = os.getenv("SUPABASE_KEY", "").strip()
        self.base_url = f"{url}/rest/v1" if url and key else ""
        self.key = key

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.key)

    def request(self, method: str, table: str, payload: Any = None, query: str = "") -> Any:
        if not self.enabled:
            return None
        url = f"{self.base_url}/{table}"
        if query:
            url += f"?{query}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("apikey", self.key)
        request.add_header("Authorization", f"Bearer {self.key}")
        request.add_header("Content-Type", "application/json")
        request.add_header("Prefer", "resolution=merge-duplicates,return=minimal")
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

    def upsert(self, table: str, row: dict[str, Any]) -> None:
        self.request("POST", table, row)

    def all(self, table: str) -> list[dict[str, Any]]:
        result = self.request("GET", table, query="select=*")
        return result if isinstance(result, list) else []


class DataStore:
    def __init__(self, db_path: str | None = None) -> None:
        configured_path = db_path or os.getenv("FINANZAS_DB_PATH", "")
        path = Path(configured_path).expanduser() if configured_path else Path.home() / ".finanzas_personales" / "finanzas.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.remote = SupabaseClient()
        self._seed()
        self.sync_from_supabase()

    @property
    def backend_label(self) -> str:
        return "Supabase conectado" if self.remote.enabled else "SQLite local"

    def close(self) -> None:
        self.db.close()

    def _seed(self) -> None:
        if self.db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            for name, color, budget in DEFAULT_CATEGORIES:
                self.db.execute("INSERT INTO categories (id, name, color, monthly_budget, created_at) VALUES (?, ?, ?, ?, ?)", (str(uuid4()), name, color, budget, _now()))
        if self.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0:
            self.db.execute("INSERT INTO accounts (id, name, institution, account_type, currency, created_at) VALUES (?, ?, ?, ?, ?, ?)", (str(uuid4()), "Cuenta principal", "Sin configurar", "cuenta", "GTQ", _now()))
        self.db.commit()

    def sync_from_supabase(self) -> None:
        if not self.remote.enabled:
            return
        try:
            for table in ("categories", "accounts", "transactions"):
                rows = self.remote.all(table)
                for row in rows:
                    self._upsert_local(table, row)
                if not rows:
                    for row in self._local_rows(table):
                        self.remote.upsert(table, row)
            self.db.commit()
        except sqlite3.Error:
            return

    def _local_rows(self, table: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute(f"SELECT * FROM {table}").fetchall()]

    def _upsert_local(self, table: str, row: dict[str, Any]) -> None:
        columns = [column[1] for column in self.db.execute(f"PRAGMA table_info({table})").fetchall()]
        values = {key: value for key, value in row.items() if key in columns}
        if not values:
            return
        keys = list(values)
        placeholders = ", ".join("?" for _ in keys)
        updates = ", ".join(f"{key}=excluded.{key}" for key in keys if key != "id")
        self.db.execute(f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders}) ON CONFLICT(id) DO UPDATE SET {updates}", [values[key] for key in keys])

    def _write_remote(self, table: str, row: dict[str, Any]) -> None:
        if self.remote.enabled:
            self.remote.upsert(table, row)

    def categories(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute("SELECT * FROM categories ORDER BY name").fetchall()]

    def accounts(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute("SELECT * FROM accounts ORDER BY name").fetchall()]

    def transactions(self, month: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        query = "SELECT t.*, a.name AS account_name, a.institution, c.name AS category_name, c.color AS category_color FROM transactions t JOIN accounts a ON a.id = t.account_id LEFT JOIN categories c ON c.id = t.category_id"
        params: list[Any] = []
        if month:
            query += " WHERE substr(t.transaction_date, 1, 7) = ?"
            params.append(month)
        query += " ORDER BY t.transaction_date DESC, t.created_at DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        return [dict(row) for row in self.db.execute(query, params).fetchall()]

    def summary(self, month: str) -> dict[str, Any]:
        rows = self.transactions(month)
        expenses = sum(row["amount"] for row in rows if row["amount"] > 0 and row["transaction_type"] == "expense")
        income = sum(abs(row["amount"]) for row in rows if row["amount"] < 0 or row["transaction_type"] == "income")
        by_category: dict[str, float] = {}
        for row in rows:
            if row["amount"] > 0 and row["transaction_type"] == "expense":
                name = row["category_name"] or "Sin clasificar"
                by_category[name] = by_category.get(name, 0) + row["amount"]
        return {"expenses": expenses, "income": income, "balance": income - expenses, "by_category": by_category, "count": len(rows)}

    def guess_category_id(self, description: str) -> str | None:
        text = description.lower()
        rules = {
            "Alimentación": ("super", "rest", "comida", "mercado", "walmart", "price smart", "food", "cafe"),
            "Transporte": ("uber", "combust", "gasolin", "parking", "parqueo", "shell", "texaco"),
            "Servicios": ("luz", "energia", "internet", "tigo", "claro", "agua", "telefono"),
            "Suscripciones": ("netflix", "spotify", "youtube", "prime", "icloud", "google"),
            "Salud": ("farmacia", "hospital", "clinica", "medic", "laboratorio"),
            "Entretenimiento": ("cine", "teatro", "juego", "steam", "restaurante"),
            "Deudas y pagos": ("pago", "cuota", "prestamo", "tarjeta", "banco"),
            "Vivienda": ("alquiler", "renta", "mantenimiento", "muebles"),
        }
        for category_name, keywords in rules.items():
            if any(keyword in text for keyword in keywords):
                row = self.db.execute("SELECT id FROM categories WHERE name = ?", (category_name,)).fetchone()
                return row[0] if row else None
        row = self.db.execute("SELECT id FROM categories WHERE name = 'Otros'").fetchone()
        return row[0] if row else None

    def add_account(self, name: str, institution: str, account_type: str, currency: str = "GTQ") -> dict[str, Any]:
        row = {"id": str(uuid4()), "name": name.strip(), "institution": institution.strip(), "account_type": account_type, "currency": currency, "current_balance": 0, "created_at": _now()}
        self.db.execute("INSERT INTO accounts (id, name, institution, account_type, currency, current_balance, created_at) VALUES (:id, :name, :institution, :account_type, :currency, :current_balance, :created_at)", row)
        self.db.commit()
        self._write_remote("accounts", row)
        return row

    def save_budget(self, category_id: str, amount: float) -> None:
        self.db.execute("UPDATE categories SET monthly_budget = ? WHERE id = ?", (amount, category_id))
        self.db.commit()
        row = dict(self.db.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone())
        self._write_remote("categories", row)

    def add_transaction(self, row: dict[str, Any]) -> bool:
        data = {"id": row.get("id", str(uuid4())), "account_id": row["account_id"], "category_id": row.get("category_id") or self.guess_category_id(row["description"]), "transaction_date": row["transaction_date"], "description": row["description"].strip(), "amount": float(row["amount"]), "transaction_type": row.get("transaction_type", "expense"), "source": row.get("source", "manual"), "source_hash": row.get("source_hash") or f"{row['account_id']}|{row['transaction_date']}|{row['description']}|{row['amount']}", "notes": row.get("notes", ""), "created_at": row.get("created_at", _now())}
        try:
            self.db.execute("INSERT INTO transactions (id, account_id, category_id, transaction_date, description, amount, transaction_type, source, source_hash, notes, created_at) VALUES (:id, :account_id, :category_id, :transaction_date, :description, :amount, :transaction_type, :source, :source_hash, :notes, :created_at)", data)
            self.db.commit()
        except sqlite3.IntegrityError:
            return False
        self._write_remote("transactions", data)
        return True

    def update_transaction_category(self, transaction_id: str, category_id: str | None) -> None:
        self.db.execute("UPDATE transactions SET category_id = ? WHERE id = ?", (category_id, transaction_id))
        self.db.commit()
        row = dict(self.db.execute("SELECT * FROM transactions WHERE id = ?", (transaction_id,)).fetchone())
        self._write_remote("transactions", row)
