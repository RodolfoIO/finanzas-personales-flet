#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from migration import migrate_existing_data  # noqa: E402
from store import DataStore  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Migra estados BAC y G&T a SQLite y Supabase.")
    parser.add_argument("source_root", type=Path, help="Carpeta que contiene cuenta BAC, tarjeta BAC y cuenta G&T")
    parser.add_argument("--db", type=Path, help="Ruta de SQLite; por defecto usa FINANZAS_DB_PATH")
    parser.add_argument("--no-sync", action="store_true", help="No subir el resultado a Supabase")
    args = parser.parse_args()

    store = DataStore(str(args.db) if args.db else None, sync_remote=False)
    try:
        report = migrate_existing_data(args.source_root, store)
        if not args.no_sync:
            store.sync_from_supabase()
        print(json.dumps({"supabase": store.remote.enabled and not args.no_sync, **report}, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
