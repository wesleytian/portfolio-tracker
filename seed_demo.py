"""Build a fake demo dataset so the app can be run and screenshotted without any real data.

Creates (or replaces) demo.db next to app.py (gitignored): investments incl. funds, exits and
write-offs, pipeline, live deals being evaluated, and a forward-to list.

Every company, fund and person in here is made up. It never opens portfolio.db.

    ./venv/bin/python seed_demo.py
    PORTFOLIO_DEMO=1 PORT=5558 ./venv/bin/python app.py      # then open http://127.0.0.1:5558
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["PORTFOLIO_DEMO"] = "1"  # must be set before importing app so it points at demo.db
os.environ.pop("PORTFOLIO_DB", None)
import app as pf  # noqa: E402

NOW = datetime.now(timezone.utc)


def seed_portfolio() -> None:
    I = lambda **kw: kw  # noqa: E731
    investments = [
        I(company="Lumen Robotics", legal_name="Lumen Robotics, Inc.", kind="direct", status="active", source="Warm intro", invested_on="2024-03-18", amount=10000, vehicle="SAFE", entry_stage="Seed", entry_valuation="$40M", current_stage="Series B", current_valuation="$600M", current_value=104000, valuation_as_of="2026-05", valuation_source="https://example.com/lumen-series-b", why="Best robotics research team I've met.", learnings="Back technical founders early in hard categories."),
        I(company="Quillstack", kind="direct", status="active", source="VC co-invest", invested_on="2024-04-23", amount=5000, vehicle="SPV", entry_stage="Series A", entry_valuation="$90M", current_stage="Series C", current_valuation="$1.2B", current_value=46000, valuation_as_of="2025-09", why="Usage growing weekly with no sales team."),
        I(company="Briefcase AI", kind="direct", status="active", source="Syndicate / SPV", invested_on="2024-07-23", amount=10000, vehicle="SPV", entry_stage="Series A", entry_valuation="$150M", current_stage="Series C", current_valuation="$900M", current_value=44000, valuation_as_of="2026-09", why="Clear wedge into law firms."),
        I(company="Briefcase AI", kind="direct", status="active", source="Secondary platform", invested_on="2025-06-02", amount=7500, vehicle="Secondary", entry_stage="Secondary", entry_valuation="$600M", current_stage="Series C", current_valuation="$900M", current_value=10500, why="Topped up on a secondary."),
        I(company="Forgepoint", kind="direct", status="active", source="Secondary platform", invested_on="2026-02-10", amount=15000, vehicle="Secondary", entry_stage="Secondary", entry_valuation="$2.9B", current_stage="Series D", current_valuation="$5B", current_value=25600, bucket="late", why="Default dev tool for every engineer I know."),
        I(company="Ledgerline", kind="direct", status="pending", source="Warm intro", amount=15000, entry_stage="Pre-seed", entry_valuation="$12M", why="Second-time founder; wiring this month."),
        I(company="Tidewater Labs", kind="direct", status="pending", source="Direct", amount=25000, entry_stage="Seed", entry_valuation="$60M", why="Climate x AI with real revenue."),
        I(company="Halo Wearables", kind="direct", status="exited", source="Event", invested_on="2021-03-08", amount=10000, vehicle="SAFE", entry_stage="Series A", entry_valuation="$85M", current_stage="Acquired", current_valuation="$12M", returned=1400, why="New device category.", learnings="Hardware + no distribution is brutal."),
        I(company="Pebblepay", kind="direct", status="exited", source="Inbound", invested_on="2020-09-14", amount=5000, vehicle="SAFE", entry_stage="Pre-seed", entry_valuation="$8M", current_stage="Acquired", current_valuation="$140M", returned=61000, why="Payments for small clinics.", gained="Acquired by a larger fintech."),
        I(company="Snackbox", kind="direct", status="written_off", source="Event", invested_on="2021-11-01", amount=10000, vehicle="SAFE", entry_stage="Seed", entry_valuation="$20M", current_value=0, why="Strong consumer brand early.", learnings="Shut down: CAC never came down."),
        I(company="Driftwood AR", kind="direct", status="written_off", source="Direct", invested_on="2022-05-20", amount=5000, vehicle="SAFE", entry_stage="Pre-seed", entry_valuation="$10M", current_value=0, why="AR glasses for field techs.", learnings="Shut down after failing to raise a Series A."),
        I(company="Meadowlark Health", kind="direct", status="active", source="Warm intro", invested_on="2023-08-30", amount=10000, vehicle="SAFE", entry_stage="Seed", entry_valuation="$25M", current_stage="Series A", current_valuation="$110M", current_value=34000, valuation_as_of="2025-12", why="Home care scheduling; founders ex-nurses."),
        I(company="Copperline", kind="direct", status="active", source="VC co-invest", invested_on="2025-01-15", amount=10000, vehicle="SPV", entry_stage="Seed", entry_valuation="$30M", current_stage="Seed", current_valuation="$30M", current_value=10000, why="Grid interconnection software."),
        I(company="Orbitly", kind="direct", status="active", source="Inbound", invested_on="2022-10-04", amount=5000, vehicle="SAFE", entry_stage="Pre-seed", entry_valuation="$9M", current_stage="Seed", current_valuation="$18M", current_value=7500, why="Satellite data marketplace."),
        I(company="Kestrel Fund II", kind="fund", status="active", source="Direct", invested_on="2020-11-03", amount=25000, vehicle="LP", vintage="2020", fund_size="$35M", called=25000, current_value=44000, returned=8000, why="High-volume pre-seed access."),
        I(company="Saltmarsh Ventures III", kind="fund", status="active", source="Inbound", invested_on="2025-04-15", amount=25000, vehicle="LP", vintage="2025", fund_size="$60M", called=10000, current_value=11500, why="First-check specialist."),
        I(company="Bluebird Capital Fund I", kind="fund", status="active", source="Warm intro", invested_on="2023-02-01", amount=50000, vehicle="LP", vintage="2023", fund_size="$120M", called=30000, current_value=36000, why="Robotics-focused seed fund; I know the GPs well."),
        I(company="Lanternfish Opportunity Fund", kind="fund", status="pending", source="Direct", amount=25000, vehicle="LP", vintage="2026", fund_size="$40M", bucket="early", why="Emerging manager, climate seed."),
    ]
    pipeline = [
        dict(name="Yara Haddad", list="tracking", note="Leaving the lab; eval tooling idea", timing="3 mo+", potential="High"),
        dict(name="Fergus Abernathy", list="tracking", note="Undergrad compiler project", timing="1 yr+", potential="Medium"),
        dict(name="Silas Mercer", list="tracking", note="Exploring after shutdown", timing="Now", potential="Medium"),
        dict(name="Ellis Navarro", list="tracking", note="Might spin out of the lab", timing="Someday", potential="High"),
        dict(name="Hana Kobayashi", list="tracking", timing="2 yr+", potential="Low"),
        dict(name="Ledgerline", list="investing", note="SAFE signed, wire pending", amount=15000, bucket="early"),
        dict(name="Glacier Compute", list="missed", note="Round filled before I could get allocation"),
        dict(name="Gridlight", list="passed", note="Capital intensive"),
        dict(name="Pocketbot", list="passed", note="Hardware risk, unclear retention"),
    ]
    evaluating = [
        dict(company="Shelfwise", round="Seed", valuation="$30M", check_size=10000, deadline=(NOW + timedelta(days=9)).date().isoformat(), source="Warm intro", next_step="Reference call with ex-manager", note="Strong team; unclear go-to-market."),
        dict(company="Northwind Robotics", round="Seed", valuation="$40M", check_size=10000, deadline=(NOW + timedelta(days=2)).date().isoformat(), source="VC co-invest", next_step="Second meeting", note="Good demo."),
        dict(company="Loomkit", round="Pre-seed", valuation="$8M", check_size=5000, source="Event", note="Consumer; waiting on retention data."),
    ]
    forward_to = [
        dict(name="Bluebird Capital", kind="vc", note="robotics, seed"), dict(name="Ironwood Partners", kind="vc"),
        dict(name="Lanternfish Ventures", kind="vc", note="climate"), dict(name="Keiko Marchetti", kind="angel", note="dev tools"),
        dict(name="Dmitri Halvorsen", kind="angel"), dict(name="Marco Lindgren", kind="angel", note="consumer"),
    ]
    with sqlite3.connect(pf.DB_PATH) as c:
        for table, rows in (("investments", investments), ("pipeline", pipeline), ("evaluating", evaluating), ("forward_to", forward_to)):
            for r in rows:
                cols, vals = pf._portfolio_values(table, r)
                c.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
        rules = dict(pf.PORTFOLIO_DEFAULT_RULES, annual_budget=120000)
        c.execute("INSERT OR REPLACE INTO portfolio_settings (key, value) VALUES ('rules', ?)", (json.dumps(rules),))


def main() -> None:
    db = Path(pf.DB_PATH).resolve()
    if db.name != "demo.db" or not pf.DEMO_MODE:
        sys.exit(f"Refusing to seed {db}: seed_demo.py only writes demo.db.")
    for ext in ("", "-wal", "-shm"):
        Path(str(db) + ext).unlink(missing_ok=True)
    pf.init_portfolio_db()
    seed_portfolio()
    with sqlite3.connect(db) as c:
        counts = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in pf.PORTFOLIO_TABLES}
    print(f"Wrote {db.name}: {counts}")
    print("Run it:  PORTFOLIO_DEMO=1 PORT=5558 ./venv/bin/python app.py   ->  http://127.0.0.1:5558")


if __name__ == "__main__":
    main()
