"""One-time migration: copy the portfolio tables out of an old combined CRM database.

Before the split, the personal CRM and this portfolio app shared one SQLite file. This copies
the portfolio tables (investments, pipeline, evaluating, forward_to, portfolio_settings) from
that file into portfolio.db, keeping ids and timestamps. The source is opened read-only and
is never modified.

    ./venv/bin/python migrate_from_crm.py ../crm/crm.db             # -> portfolio.db
    ./venv/bin/python migrate_from_crm.py ../crm/crm.db --force     # replace an existing portfolio.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path

TABLES = ["investments", "pipeline", "evaluating", "forward_to", "portfolio_settings"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", help="path to the old combined crm.db")
    p.add_argument("dest", nargs="?", default=str(Path(__file__).parent / "portfolio.db"))
    p.add_argument("--force", action="store_true", help="overwrite dest if it already exists")
    args = p.parse_args()

    src_path, dest = Path(args.source).resolve(), Path(args.dest).resolve()
    if not src_path.exists():
        sys.exit(f"{src_path} not found")
    if src_path == dest:
        sys.exit("source and destination are the same file")
    if dest.exists():
        if not args.force:
            sys.exit(f"{dest} already exists; pass --force to replace it")
        for ext in ("", "-wal", "-shm"):
            Path(str(dest) + ext).unlink(missing_ok=True)

    # Snapshot the source through SQLite's backup API (read-only URI) so a running CRM server
    # writing to it can't give us a torn copy.
    src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
    snap = sqlite3.connect(":memory:")
    src.backup(snap)
    src.close()

    have = {r[0] for r in snap.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing = [t for t in TABLES if t not in have]
    if missing:
        sys.exit(f"source has no {', '.join(missing)} table(s); is this the right file?")

    out = sqlite3.connect(dest)
    counts = {}
    for t in TABLES:
        (ddl,) = snap.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
        out.execute(ddl)
        cols = [r[1] for r in snap.execute(f"PRAGMA table_info({t})")]
        rows = snap.execute(f"SELECT {', '.join(cols)} FROM {t}").fetchall()
        out.executemany(f"INSERT INTO {t} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", rows)
        counts[t] = len(rows)
    # Keep AUTOINCREMENT counters, so ids of deleted rows are never reused.
    for name, seq in snap.execute("SELECT name, seq FROM sqlite_sequence"):
        if name in TABLES:
            out.execute("DELETE FROM sqlite_sequence WHERE name=?", (name,))
            out.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (name, seq))
    out.commit()

    # Verify: every table has the same row count and identical contents.
    for t in TABLES:
        a = snap.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
        b = out.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
        if a != b:
            sys.exit(f"verification failed for {t}: {len(a)} source rows vs {len(b)} copied")
    out.close()
    snap.close()
    print(f"Copied into {dest}: " + ", ".join(f"{t}={n}" for t, n in counts.items()))


if __name__ == "__main__":
    main()
