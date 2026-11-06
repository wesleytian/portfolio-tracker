"""Private investments: direct and fund (LP) positions, pacing, a public-market benchmark,
live deals being evaluated, pipeline and who to forward deals to.

Local Flask app on one SQLite file (portfolio.db, gitignored).
"""
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

APP_DIR = Path(__file__).parent
# PORTFOLIO_DEMO=1 runs against the fake data from seed_demo.py (demo.db) and never opens portfolio.db.
DEMO_MODE = os.environ.get("PORTFOLIO_DEMO") == "1"
DB_PATH = Path(os.environ.get("PORTFOLIO_DB") or APP_DIR / ("demo.db" if DEMO_MODE else "portfolio.db"))

app = Flask(__name__, static_folder="static", static_url_path="/static")


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Portfolio: my angel investments, pipeline, who to forward deals to.
# Deal sources and forward-to names are plain text: no links to any contacts app.
# ---------------------------------------------------------------------------

# table -> {column: kind}. kinds: text, int, date
PORTFOLIO_TABLES = {
    "investments": {
        "company": "text", "legal_name": "text", "kind": "text", "status": "text", "bucket": "text",
        "invested_on": "date", "amount": "int", "vehicle": "text",
        "entry_valuation": "text", "entry_stage": "text",
        "current_valuation": "text", "current_stage": "text", "current_value": "int", "returned": "int",
        "valuation_as_of": "text", "valuation_source": "text",
        # Funds (LP positions): amount = committed; called = paid in so far.
        "vintage": "text", "fund_size": "text", "called": "int",
        "source": "text", "why": "text", "learnings": "text", "gained": "text", "notes": "text",
    },
    # amount + bucket = money set aside for a deal I'm investing in but haven't wired yet
    # timing: when I think a tracked person might start a company (Now, 3 mo+, 6 mo+, ...)
    "pipeline": {"name": "text", "list": "text", "note": "text", "amount": "int", "bucket": "text", "timing": "text", "potential": "text"},
    "forward_to": {"name": "text", "kind": "text", "note": "text"},
    # Live deals I'm deciding on. Commit turns one into a pending investment; Pass moves it to pipeline/passed.
    "evaluating": {"company": "text", "round": "text", "valuation": "text", "check_size": "int", "deadline": "date",
                   "source": "text", "next_step": "text", "note": "text"},
}
PORTFOLIO_DEFAULT_RULES = {
    "annual_budget": 100000,
    "early": {"check": 10000, "per_year": 15},
    "mid": {"check": 25000, "per_year": 5},
    "late": {"check": 50000, "per_year": 5},
}


def init_portfolio_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        for table, cols in PORTFOLIO_TABLES.items():
            col_sql = ", ".join(f"{c} {'INTEGER' if k == 'int' else 'TEXT'}" for c, k in cols.items())
            conn.execute(
                f"""CREATE TABLE IF NOT EXISTS {table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, {col_sql},
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP)"""
            )
            have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for c, k in cols.items():
                if c not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {c} {'INTEGER' if k == 'int' else 'TEXT'}")
        conn.execute("CREATE TABLE IF NOT EXISTS portfolio_settings (key TEXT PRIMARY KEY, value TEXT)")


def _portfolio_values(table: str, data: dict) -> tuple[list[str], list]:
    cols, vals = [], []
    for c, kind in PORTFOLIO_TABLES[table].items():
        if c not in data:
            continue
        v = data[c]
        if isinstance(v, str):
            v = v.strip()
        if v in ("", None):
            v = None
        elif kind == "int":
            try:
                v = int(float(str(v).replace(",", "").replace("$", "")))
            except ValueError:
                raise ValueError(f"{c}: '{v}' is not a number")
        elif kind == "date":
            try:
                v = datetime.fromisoformat(str(v)).date().isoformat()
            except ValueError:
                raise ValueError(f"{c}: '{v}' is not a date (YYYY-MM-DD)")
        cols.append(c); vals.append(v)
    return cols, vals


@app.route("/")
def portfolio_page():
    return send_from_directory(APP_DIR / "static", "portfolio.html")


@app.route("/portfolio")
def portfolio_redirect():
    from flask import redirect
    return redirect("/" + (f"?{request.query_string.decode()}" if request.query_string else ""))


@app.route("/api/portfolio/settings", methods=["GET", "PUT"])
def portfolio_settings():
    with _db() as conn:
        if request.method == "PUT":
            conn.execute(
                "INSERT OR REPLACE INTO portfolio_settings (key, value) VALUES ('rules', ?)",
                (json.dumps(request.get_json(force=True).get("rules")),),
            )
        row = conn.execute("SELECT value FROM portfolio_settings WHERE key='rules'").fetchone()
    return jsonify({"rules": json.loads(row["value"]) if row else PORTFOLIO_DEFAULT_RULES})


@app.route("/api/portfolio/<table>", methods=["GET", "POST"])
def portfolio_rows(table: str):
    if table not in PORTFOLIO_TABLES:
        return jsonify({"error": "unknown table"}), 404
    with _db() as conn:
        if request.method == "POST":
            try:
                cols, vals = _portfolio_values(table, request.get_json(force=True))
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
            if not cols:
                return jsonify({"error": "empty row"}), 400
            cur = conn.execute(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals)
            return jsonify(dict(conn.execute(f"SELECT * FROM {table} WHERE id=?", (cur.lastrowid,)).fetchone())), 201
        return jsonify([dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")])


@app.route("/api/portfolio/<table>/<int:row_id>", methods=["PUT", "DELETE"])
def portfolio_row(table: str, row_id: int):
    if table not in PORTFOLIO_TABLES:
        return jsonify({"error": "unknown table"}), 404
    with _db() as conn:
        if request.method == "DELETE":
            conn.execute(f"DELETE FROM {table} WHERE id=?", (row_id,))
            return jsonify({"ok": True})
        try:
            cols, vals = _portfolio_values(table, request.get_json(force=True))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if cols:
            conn.execute(
                f"UPDATE {table} SET {', '.join(c + '=?' for c in cols)}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                vals + [row_id],
            )
        row = conn.execute(f"SELECT * FROM {table} WHERE id=?", (row_id,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error": "not found"}), 404)


VALUATION_PROMPT = """Find the most recent publicly reported valuation and funding stage for this private company I invested in.

Company: {company}{legal}
What I know: invested {invested_on} at {entry_stage} stage, valuation then {entry_valuation}. Notes: {notes}

Search the web; one or two searches are usually enough. Names like this are often ambiguous, so make sure the company you find matches what I know (stage and valuation at the time I invested should be consistent with its history). Prefer funding announcements, reputable press (TechCrunch, Bloomberg, The Information, Reuters) and the company's own posts. A secondary-market or tender price counts if it's the most recent figure; say so in the summary.

If you can't find anything newer than what I already know, or you're not confident it's the same company, say found=false. Never estimate or guess a number.

End your reply with only this JSON object:
{{"found": true|false, "valuation": "<short post-money figure only, e.g. $350B or $45M, or null>", "valuation_usd": <number or null>, "stage": "<e.g. Series A, Seed, Public, Acquired, or null>", "as_of": "<YYYY-MM or YYYY-MM-DD, or null>", "source_url": "<url or null>", "note": "<only if there is a caveat, under 6 words, e.g. pending Series C, IPO filed, tender offer price, acquired by X; otherwise null>"}}"""


def _lookup_valuation(inv: dict) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(f"ANTHROPIC_API_KEY not set. Edit {APP_DIR / '.env'} and restart.")
    from anthropic import Anthropic
    client = Anthropic(api_key=key)
    prompt = VALUATION_PROMPT.format(
        company=inv["company"],
        legal=f" (legal name: {inv['legal_name']})" if inv.get("legal_name") else "",
        invested_on=inv.get("invested_on") or "unknown date",
        entry_stage=inv.get("entry_stage") or "unknown",
        entry_valuation=inv.get("entry_valuation") or "unknown",
        notes=inv.get("notes") or "none",
    )
    messages = [{"role": "user", "content": prompt}]
    # Web search can pause a long turn; resume by sending the partial turn back (max a few times).
    for _ in range(4):
        resp = client.beta.messages.create(
            model="claude-opus-5-5",
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
            output_config={"effort": "low"},
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}],
            messages=messages,
        )
        if resp.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": resp.content}]
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this lookup")
    text = "".join(b.text for b in resp.content if b.type == "text")
    start, end = text.rfind("{"), text.rfind("}")
    # The JSON object is the last thing in the reply; take the outermost braces before the end.
    depth, i = 0, end
    while i >= 0:
        depth += text[i] == "}"
        depth -= text[i] == "{"
        if depth == 0:
            start = i
            break
        i -= 1
    try:
        out = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        raise RuntimeError("Couldn't read the lookup result")
    return out


@app.route("/api/portfolio/investments/<int:row_id>/lookup", methods=["POST"])
def portfolio_lookup(row_id: int):
    """Propose a fresh valuation/stage from a web search. Writes nothing — the page shows
    the proposal and saves only what you accept."""
    with _db() as conn:
        row = conn.execute("SELECT * FROM investments WHERE id=?", (row_id,)).fetchone()
    if not row:
        return jsonify({"error": "not found"}), 404
    try:
        return jsonify(_lookup_valuation(dict(row)))
    except Exception as e:  # surface API/key problems to the page instead of a bare 500
        return jsonify({"error": str(e)}), 502


# ---------------------------------------------------------------------------
# Public-market benchmark: what the same dollars, on the same dates, would be worth in an index.
# ---------------------------------------------------------------------------

BENCHMARKS = {
    "sp500": ("S&P 500", ["SPY"]),
    "nasdaq": ("Nasdaq-100", ["QQQ"]),
    "mag7": ("Magnificent 7", ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]),
    "nvda": ("Nvidia", ["NVDA"]),
}
# Weekly is plenty for this comparison, and Yahoo is slow (~9s per symbol for 10y weekly), so
# prices are fetched once a day and kept on disk; the server warms them in the background at start.
PRICE_CACHE_FILE = APP_DIR / "price_cache.json"
_PRICE_CACHE: dict[str, tuple[str, list[str], list[float]]] = {}
try:
    _PRICE_CACHE.update({k: tuple(v) for k, v in json.loads(PRICE_CACHE_FILE.read_text()).items()})
except (OSError, ValueError):
    pass


def _price_series(sym: str) -> tuple[list[str], list[float]]:
    """Weekly adjusted closes (dividends reinvested) for ~10 years, from Yahoo Finance. Cached per day."""
    import urllib.request
    today = datetime.now().strftime("%Y-%m-%d")
    hit = _PRICE_CACHE.get(sym)
    if hit and hit[0] == today:
        return hit[1], hit[2]
    req = urllib.request.Request(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=10y&interval=1wk",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    import ssl, certifi  # python.org's macOS Python has no system CA certs; certifi ships with the SDK
    with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context(cafile=certifi.where())) as r:
        res = json.load(r)["chart"]["result"][0]
    pairs = [
        (datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d"), v)
        for t, v in zip(res["timestamp"], res["indicators"]["adjclose"][0]["adjclose"]) if v
    ]
    dates, closes = [d for d, _ in pairs], [v for _, v in pairs]
    _PRICE_CACHE[sym] = (today, dates, closes)
    try:
        PRICE_CACHE_FILE.write_text(json.dumps(_PRICE_CACHE))
    except OSError:
        pass
    return dates, closes


def _all_series(syms: list[str]) -> dict[str, tuple[list[str], list[float]]]:
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(syms, pool.map(_price_series, syms)))


def _warm_prices() -> None:
    try:
        _all_series(sorted({s for _, syms in BENCHMARKS.values() for s in syms}))
    except Exception as e:
        print(f"[prices] warm-up failed: {e}", flush=True)


@app.route("/api/benchmark/<key>", methods=["POST"])
def benchmark(key: str):
    """Body {dates: [YYYY-MM-DD...]}. Returns each symbol's close on (or just before) each date,
    plus the latest close, so the page can compute what each check would be worth in the index."""
    import bisect
    if key not in BENCHMARKS:
        return jsonify({"error": "unknown benchmark"}), 404
    label, syms = BENCHMARKS[key]
    dates = [d for d in (request.get_json(force=True).get("dates") or []) if d]
    try:
        series = _all_series(syms)
    except Exception as e:
        return jsonify({"error": f"Couldn't load prices: {e}"}), 502
    at = {}
    for d in dates:
        at[d] = {}
        for s, (ds, cs) in series.items():
            i = bisect.bisect_right(ds, d) - 1
            at[d][s] = cs[max(i, 0)]
    return jsonify({
        "label": label, "symbols": syms,
        "as_of": min(ds[-1] for ds, _ in series.values()),
        "latest": {s: cs[-1] for s, (_, cs) in series.items()},
        "at": at,
    })


BACKUP_DIR = APP_DIR / "backups"
BACKUP_KEEP = 30


def backup_db() -> Path | None:
    """One consistent copy of the database per day in backups/ (gitignored), keeping the last 30.
    Uses SQLite's online backup so it's safe while the server is writing."""
    BACKUP_DIR.mkdir(exist_ok=True)
    dest = BACKUP_DIR / f"{DB_PATH.stem}-{datetime.now().strftime('%Y-%m-%d')}.db"
    if dest.exists():
        return None
    with sqlite3.connect(DB_PATH) as src, sqlite3.connect(dest) as dst:
        src.backup(dst)
    for old in sorted(BACKUP_DIR.glob(f"{DB_PATH.stem}-*.db"))[:-BACKUP_KEEP]:
        old.unlink()
    return dest


def _backup_loop() -> None:
    while True:
        try:
            made = backup_db()
            if made:
                print(f"[backup] wrote {made.name}", flush=True)
        except Exception as e:  # never let a backup problem take the server down
            print(f"[backup] failed: {e}", flush=True)
        time.sleep(6 * 60 * 60)


@app.route("/api/portfolio/investments.csv")
def portfolio_csv():
    import csv, io
    cols = ["company", "status", "kind", "source", "invested_on", "amount", "called", "vehicle",
            "entry_stage", "entry_valuation", "current_stage", "current_valuation", "current_value",
            "returned", "vintage", "fund_size", "why", "valuation_as_of", "valuation_source"]
    with _db() as conn:
        rows = conn.execute(f"SELECT {', '.join(cols)} FROM investments ORDER BY invested_on").fetchall()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(cols)
    w.writerows([tuple(r) for r in rows])
    return app.response_class(buf.getvalue(), mimetype="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=private-investments-{datetime.now():%Y-%m-%d}.csv"})

if __name__ == "__main__":
    init_portfolio_db()
    import threading
    if not DEMO_MODE:
        threading.Thread(target=_backup_loop, daemon=True).start()
    threading.Thread(target=_warm_prices, daemon=True).start()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5557)), debug=False)
