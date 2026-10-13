"""One-time push of the verified local state to the hosted Turso DB.

Copies every table (discovered + system) row-for-row, preserving ids so
provenance references hold. Refuses to run against a non-empty remote
unless --force (which wipes remote tables first).

Usage: set -a && . ../.env && set +a && python3 push_turso.py [--force]
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "populate"))
import db as dblib

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local",
                    default=str(HERE.parent / "populate" / "out" / "state.sqlite"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    schema = dblib.load_schema()
    remote = dblib.TursoDB()
    dblib.create_tables(remote, schema)
    tables = list(schema["tables"]) + ["catchall", "ingest_log"]

    existing = remote.execute('SELECT COUNT(*) AS c FROM "dogs"')[0]["c"]
    if int(existing) > 0:
        if not args.force:
            print(f"remote already has data (dogs={existing}); rerun with --force to wipe+repush")
            sys.exit(1)
        for t in tables:
            remote.execute(f'DELETE FROM "{t}"')
        print("remote wiped")

    local = sqlite3.connect(args.local)
    local.row_factory = sqlite3.Row
    for t in tables:
        rows = [dict(r) for r in local.execute(f'SELECT * FROM "{t}"')]
        if not rows:
            print(f"{t}: 0 rows")
            continue
        cols = list(rows[0].keys())
        sql = (f'INSERT INTO "{t}" ({", ".join(chr(34)+c+chr(34) for c in cols)}) '
               f'VALUES ({", ".join("?" for _ in cols)})')
        stmts = [(sql, [r[c] for c in cols]) for r in rows]
        for i in range(0, len(stmts), 50):
            remote.execute_batch(stmts[i:i + 50])
        got = remote.execute(f'SELECT COUNT(*) AS c FROM "{t}"')[0]["c"]
        status = "OK" if int(got) == len(rows) else "MISMATCH"
        print(f"{t}: pushed {len(rows)} | remote now {got} [{status}]")
    print("push complete")


if __name__ == "__main__":
    main()
