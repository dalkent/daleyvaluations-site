#!/usr/bin/env python3
"""
build_site.py
─────────────
Renders the Daley Valuations public site from etoro_master.json.

Reads:
  C:\\Users\\Neil\\ClaudeCode\\eToro\\data\\etoro_master.json (canonical valuation data)

Writes (relative to repo root):
  index.html           — homepage, the live FTSE Valuation Tracker
  methodology.html     — methodology page (moves from / to /methodology when build runs)
  ticker/<ticker>.html — one page per stock (114 expected)
  sitemap.xml          — for SEO

Run manually:
  python scripts/build_site.py

Run from scheduled task:
  Wired into ftse-tracker-weekly (Mon 5pm) so the site rebuilds whenever new valuations land.

Status:
  STUB. Fill in step by step. See PLAN-STAGE-2.md for the build sequence.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
DATA_FILE = Path("C:/Users/Neil/ClaudeCode/eToro/data/etoro_master.json")
OUTPUT_TICKER_DIR = REPO_ROOT / "ticker"

# Stale-data threshold: if etoro_master.json is older than this many days,
# render the site with a "Data refresh in progress" banner instead of failing.
STALE_DATA_DAYS = 14

# Public vs private record sets in etoro_master.json
PUBLIC_RECORD_PATHS = (
    ("assumptions", "valuations"),       # ticker, three model values, blended target, signal
    ("sheets", "watchlist", "objects"),   # live price, value ratio, daily change, range
    ("sheets", "tickers", "objects"),     # asset metadata
)
PRIVATE_RECORD_PATHS = (
    ("sheets", "portfolio", "objects"),       # holdings, P&L, units — never publish
    ("sheets", "closed_positions", "objects"), # trade history — handle separately
)


def load_data() -> dict:
    """Load etoro_master.json or fail loudly."""
    if not DATA_FILE.exists():
        sys.exit(f"ERROR: data file not found at {DATA_FILE}")
    with open(DATA_FILE) as f:
        return json.load(f)


def get_records(data: dict, path: tuple) -> list:
    """Walk a path tuple into the nested JSON. Returns the list of dicts at the end."""
    obj = data
    for key in path:
        obj = obj.get(key, {})
    return obj if isinstance(obj, list) else []


def join_valuations_with_prices(data: dict) -> list[dict]:
    """
    Merge assumptions.valuations (model outputs) with sheets.watchlist.objects (live prices).

    Returns one dict per ticker with the full set of public fields needed to render
    a tracker row and a per-ticker page.
    """
    valuations = get_records(data, ("assumptions", "valuations"))
    watchlist = get_records(data, ("sheets", "watchlist", "objects"))
    tickers = get_records(data, ("sheets", "tickers", "objects"))

    # Build lookup by ticker
    watch_by_ticker = {r.get("eToro Ticker", "").strip(): r for r in watchlist}
    meta_by_ticker = {r.get("eToro Ticker", "").strip(): r for r in tickers}

    merged = []
    for v in valuations:
        ticker = v.get("Ticker", "").strip()
        if not ticker:
            continue

        watch = watch_by_ticker.get(ticker, {})
        meta = meta_by_ticker.get(ticker, {})

        merged.append({
            "ticker": ticker,
            "company": v.get("Company", "").strip(),
            "sector": v.get("Sector", "").strip(),
            "currency": meta.get("Currency", ""),
            "beta": v.get("Beta"),
            "wacc": v.get("WACC"),
            "g1": v.get("g1 (5yr Growth)"),
            "g2": v.get("g2 (Terminal)"),
            "val_dcf": v.get("Val 1 (DCF / Banks:DDM)"),
            "val_ddm": v.get("Val 2 (DDM / Banks:P/B / AM:P/B)"),
            "val_epv": v.get("Val 3 (EPV / Fin:Earn Cap / GI:P/TB)"),
            "blended_target": v.get("Blended Target (GBP / USD)"),
            "model_method": v.get("Model / Method", ""),
            "last_updated": v.get("Last Updated", ""),
            "prev_signal": v.get("Prev Signal", ""),
            "current_signal": v.get("Current Signal", ""),
            "live_price": watch.get("Live Price (Local) ¹"),
            "value_ratio": watch.get("Value Ratio"),
            "daily_change_pct": watch.get("Daily Chg %"),
            "high_52w": watch.get("52W High (Local) ¹"),
            "low_52w": watch.get("52W Low (Local) ¹"),
            "range_position": watch.get("Range Position"),
        })

    return merged


def signal_for(value_ratio: float | None) -> tuple[str, str]:
    """
    Map a value ratio to (signal_label, css_class).
    Matches the thresholds documented in the methodology page.
    """
    if value_ratio is None:
        return "N/A", "na"
    if value_ratio >= 1.25:
        return "Strong Buy", "sb"
    if value_ratio >= 1.10:
        return "Buy", "b"
    if value_ratio >= 0.90:
        return "Fair Value", "fv"
    if value_ratio >= 0.75:
        return "Sell", "s"
    return "Strong Sell", "ss"


def to_float(v) -> float | None:
    """Coerce a value (which may be float, int, str, or empty) to float or None."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def sanity_check(records: list[dict]) -> list[str]:
    """
    Flag suspicious records before rendering.

    Returns a list of warnings. If any returned, the build should still proceed
    but the warnings get logged so Neil can review them.
    """
    warnings = []
    for r in records:
        vr = to_float(r.get("value_ratio"))
        ticker = r.get("ticker")
        if vr is not None:
            if vr < 0.2:
                warnings.append(f"{ticker}: value ratio {vr:.3f} is implausibly low, review")
            if vr > 5.0:
                warnings.append(f"{ticker}: value ratio {vr:.3f} is implausibly high, review")
        if not r.get("company"):
            warnings.append(f"{ticker}: missing company name")
    return warnings


def build_tracker_page(records: list[dict]) -> str:
    """Render the homepage (the live tracker table). NOT YET IMPLEMENTED."""
    # TODO: load templates/tracker.html, render with Jinja2
    raise NotImplementedError("tracker page renderer pending")


def build_ticker_page(record: dict) -> str:
    """Render one per-ticker page. NOT YET IMPLEMENTED."""
    # TODO: load templates/ticker.html, render with Jinja2
    raise NotImplementedError("ticker page renderer pending")


def build_methodology_page() -> str:
    """Render the methodology page. NOT YET IMPLEMENTED."""
    # TODO: copy index.html content into a new methodology template,
    # add navigation header, output as methodology.html
    raise NotImplementedError("methodology page renderer pending")


def build_sitemap(records: list[dict]) -> str:
    """Render sitemap.xml listing every page on the site."""
    base = "https://daleyvaluations.com"
    today = datetime.now().strftime("%Y-%m-%d")
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    # Static pages
    for path in ["", "methodology"]:
        lines.append(f"  <url><loc>{base}/{path}</loc><lastmod>{today}</lastmod></url>")

    # Per-ticker pages
    for r in records:
        slug = r["ticker"].lower().replace(".", "-")
        lines.append(f"  <url><loc>{base}/ticker/{slug}</loc><lastmod>{today}</lastmod></url>")

    lines.append("</urlset>")
    return "\n".join(lines)


def main():
    print(f"[{datetime.now().isoformat()}] Building daleyvaluations.com")
    data = load_data()
    records = join_valuations_with_prices(data)
    print(f"  Joined {len(records)} ticker records from valuations + watchlist")

    warnings = sanity_check(records)
    if warnings:
        print(f"  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")
        # In production, consider failing the build if warnings exceed a threshold
    else:
        print(f"  Sanity check passed")

    # The actual rendering is not yet implemented. This stub validates the data
    # pipeline and proves the join works.
    print(f"  Render stages pending. See PLAN-STAGE-2.md for the build sequence.")


if __name__ == "__main__":
    main()
