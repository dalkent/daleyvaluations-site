#!/usr/bin/env python3
"""build_site.py - Daley Valuations site builder. v2 with Held badge + What Changed panel."""
import argparse, json, sys, time, os, shutil, re
from collections import Counter
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULT_DATA_FILE = Path("C:/Users/Neil/ClaudeCode/eToro/data/etoro_master.json")
DEFAULT_PORTFOLIO_FILE = Path("C:/Users/Neil/ClaudeCode/eToro/data/combined_portfolio.json")
PRICE_CACHE_FILE = REPO_ROOT / ".price_cache.json"
PRICE_CACHE_TTL_HOURS = 1

env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def to_float(v):
    if v is None or v == "": return None
    try: return float(v)
    except (TypeError, ValueError): return None


def get_records(data, path):
    obj = data
    for key in path:
        obj = obj.get(key, {}) if isinstance(obj, dict) else {}
    return obj if isinstance(obj, list) else []


def signal_for(vr):
    if vr is None: return "N/A", "na"
    if vr >= 1.25: return "Strong Buy", "sb"
    if vr >= 1.10: return "Buy", "b"
    if vr >= 0.90: return "Fair Value", "fv"
    if vr >= 0.75: return "Sell", "s"
    return "Strong Sell", "ss"


def slug_for(ticker):
    return ticker.lower().replace(".", "-").replace("/", "-")


def fmt_price(v, currency=""):
    if v is None: return "—"
    if currency in ("GBp", "GBX"): return f"{v:,.1f}p"
    if currency == "USD": return f"${v:,.2f}"
    if currency == "GBP": return f"£{v:,.2f}"
    return f"{v:,.2f}"


def fmt_target(v, currency=""):
    if v is None: return "—"
    if currency in ("GBp", "GBX"): return f"{v * 100:,.1f}p"
    if currency == "USD": return f"${v:,.2f}"
    if currency == "GBP": return f"£{v:,.2f}"
    return f"{v:,.2f}"


def fmt_target_smart(v, currency, live_price):
    if v is None: return "—"
    if currency not in ("GBp", "GBX"): return fmt_target(v, currency)
    if live_price and live_price > 0:
        as_decimal = v * 100
        as_pence = v
        if 0.2 <= as_decimal / live_price <= 5.0:
            return f"{as_decimal:,.1f}p"
        if 0.2 <= as_pence / live_price <= 5.0:
            return f"{as_pence:,.1f}p"
    return f"{v * 100:,.1f}p"


def fmt_vr(v):
    if v is None: return "—"
    return f"{v:.2f}"


def fmt_pct(v, decimals=2):
    if v is None: return "—"
    return f"{v * 100:.{decimals}f}%"


def fmt_change(prev, current):
    if not prev or not current or prev == current:
        return '<span class="change-flat">—</span>'
    order = ["Strong Sell", "Sell", "Fair Value", "Buy", "Strong Buy"]
    try:
        prev_i = order.index(prev)
        curr_i = order.index(current)
    except ValueError:
        return '<span class="change-flat">—</span>'
    if curr_i > prev_i:
        return f'<span class="change-up">{prev} ↑ {current}</span>'
    return f'<span class="change-down">{prev} ↓ {current}</span>'


def load_data(data_file):
    if not data_file.exists():
        sys.exit(f"ERROR: data file not found at {data_file}")
    with open(data_file, encoding="utf-8") as f:
        raw = f.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        for closer in ("}", "]}", "]}}", "}}"):
            try:
                data = json.loads(raw + closer)
                print(f"  WARNING: data file truncated, recovered by appending '{closer}'")
                return data
            except json.JSONDecodeError:
                continue
        sys.exit("ERROR: data file is corrupt and could not be auto-repaired. Re-run valuation.py.")


def load_held_tickers(portfolio_file):
    """Read combined_portfolio.json and return set of ticker symbols (yahoo format) currently held.

    The file may contain two concatenated JSON snapshots; take the first.
    Returns just the set of tickers - never units, P&L, entry prices, or any private detail.
    """
    if not portfolio_file.exists():
        print(f"  WARNING: portfolio file not found at {portfolio_file} - Held badges will be omitted")
        return set()
    try:
        with open(portfolio_file, encoding="utf-8") as f:
            raw = f.read()
        decoder = json.JSONDecoder()
        data, _ = decoder.raw_decode(raw)
        held = set()
        for h in data.get("holdings", []):
            # eToro holdings only - T212 is private and not represented on the public site
            if (h.get("broker") or "").lower() != "etoro":
                continue
            yahoo = (h.get("yahoo") or "").strip().upper()
            if yahoo:
                held.add(yahoo)
        print(f"  Loaded {len(held)} held tickers from portfolio file")
        return held
    except Exception as e:
        print(f"  WARNING: could not parse portfolio file ({e}) - Held badges will be omitted")
        return set()


def join_records(data):
    valuations = get_records(data, ("assumptions", "valuations"))
    watchlist = get_records(data, ("sheets", "watchlist", "objects"))
    tickers = get_records(data, ("sheets", "tickers", "objects"))
    watch_by = {(r.get("eToro Ticker") or "").strip(): r for r in watchlist}
    meta_by = {(r.get("eToro Ticker") or "").strip(): r for r in tickers}

    merged = []
    for v in valuations:
        ticker = (v.get("Ticker") or "").strip()
        if not ticker: continue
        watch = watch_by.get(ticker, {})
        meta = meta_by.get(ticker, {})
        yt = (meta.get("Yahoo Finance Ticker") or ticker).strip().upper()
        merged.append({
            "ticker": ticker,
            "yahoo_ticker": yt,
            "company": (v.get("Company") or "").strip(),
            "sector": (v.get("Sector") or "").strip(),
            "currency": (watch.get("Currency") or meta.get("Currency") or ("GBp" if (meta.get("Market") or "") == "FTSE" else "")),
            "market": meta.get("Market", ""),
            "asset_type": meta.get("Asset Type", ""),
            "beta": to_float(v.get("Beta")),
            "wacc": to_float(v.get("WACC")),
            "g1": to_float(v.get("g1 (5yr Growth)")),
            "g2": to_float(v.get("g2 (Terminal)")),
            "val_dcf": to_float(v.get("Val 1 (DCF / Banks:DDM)")),
            "val_ddm": to_float(v.get("Val 2 (DDM / Banks:P/B / AM:P/B)")),
            "val_epv": to_float(v.get("Val 3 (EPV / Fin:Earn Cap / GI:P/TB)")),
            "blended_target": to_float(v.get("Blended Target (GBP / USD)")),
            "model_method": v.get("Model / Method") or "",
            "last_updated": v.get("Last Updated", ""),
            "prev_signal": v.get("Prev Signal", ""),
            "current_signal": v.get("Current Signal", ""),
            "live_price": to_float(watch.get("Live Price (Local) ¹")),
            "value_ratio": to_float(watch.get("Value Ratio")),
        })
    return merged


def filter_public(records):
    return [r for r in records if r.get("market") == "FTSE" and r.get("asset_type") == "Equity" and r.get("sector") != "Corp Bonds" and r.get("current_signal")]


def fetch_live_prices(records, force_refresh=False):
    if not force_refresh and PRICE_CACHE_FILE.exists():
        try:
            with open(PRICE_CACHE_FILE) as f:
                cache = json.load(f)
            cached_at = datetime.fromisoformat(cache.get("cached_at", "1970-01-01"))
            age_hours = (datetime.now() - cached_at).total_seconds() / 3600
            if age_hours < PRICE_CACHE_TTL_HOURS:
                print(f"  Using price cache (age: {age_hours:.1f} hours)")
                return cache.get("prices", {})
        except Exception as e:
            print(f"  Cache read failed: {e}, fetching fresh")

    print(f"  Fetching live prices from Yahoo Finance...")
    import yfinance as yf
    tickers = [r["yahoo_ticker"] for r in records]
    try:
        data = yf.download(tickers, period="2d", interval="1d", progress=False, auto_adjust=False, threads=True)
    except Exception as e:
        print(f"  ERROR: yfinance batch download failed: {e}")
        return {}

    prices = {}
    if not data.empty and "Close" in data.columns.get_level_values(0):
        close = data["Close"]
        latest = close.iloc[-1] if len(close) else None
        if latest is not None:
            for ticker in tickers:
                if ticker in latest.index:
                    val = latest[ticker]
                    if val is not None and val == val:
                        prices[ticker] = float(val)

    missing = [t for t in tickers if t not in prices]
    if missing:
        print(f"  Retrying {len(missing)} missed ticker(s) individually: {missing[:5]}")
        for t in missing:
            try:
                hist = yf.Ticker(t).history(period="2d")
                if not hist.empty and "Close" in hist.columns:
                    val = hist["Close"].iloc[-1]
                    if val is not None and val == val:
                        prices[t] = float(val)
            except Exception as e:
                print(f"    {t}: retry failed: {e}")

    try:
        with open(PRICE_CACHE_FILE, "w") as f:
            json.dump({"cached_at": datetime.now().isoformat(), "prices": prices}, f, indent=2)
    except Exception as e:
        print(f"  Cache write failed (non-fatal): {e}")

    print(f"  Fetched {len(prices)}/{len(tickers)} live prices")
    return prices


def apply_live_prices(records, live_prices):
    for r in records:
        live = live_prices.get(r["yahoo_ticker"])
        if live is None: continue
        r["live_price"] = live
        target = r.get("blended_target")
        if target is None or live <= 0: continue
        currency = r.get("currency", "")
        if currency in ("GBp", "GBX"):
            vr_decimal = (target * 100) / live
            vr_already_pence = target / live
            if 0.2 <= vr_decimal <= 5.0: r["value_ratio"] = vr_decimal
            elif 0.2 <= vr_already_pence <= 5.0: r["value_ratio"] = vr_already_pence
            else: r["value_ratio"] = vr_decimal
        else:
            r["value_ratio"] = target / live
    return records


def sanity_check(records):
    warnings = []
    for r in records:
        vr = r["value_ratio"]
        if vr is not None:
            if vr < 0.2: warnings.append(f"{r['ticker']}: VR {vr:.3f} implausibly low")
            if vr > 5.0: warnings.append(f"{r['ticker']}: VR {vr:.3f} implausibly high")
        if not r["company"]: warnings.append(f"{r['ticker']}: missing company name")
    return warnings


def shape_for_tracker(records, held_tickers):
    out = []
    for r in records:
        signal_label, signal_class = signal_for(r["value_ratio"])
        currency = r.get("currency", "")
        is_held = r["ticker"].upper() in held_tickers or r["yahoo_ticker"].upper() in held_tickers
        out.append({
            "ticker": r["ticker"],
            "slug": slug_for(r["ticker"]),
            "company": r["company"],
            "sector": r["sector"],
            "currency": currency,
            "is_held": is_held,
            "price_raw": r["live_price"],
            "target_raw": r["blended_target"],
            "value_ratio_raw": r["value_ratio"],
            "price_display": fmt_price(r["live_price"], currency),
            "target_display": fmt_target_smart(r["blended_target"], currency, r["live_price"]),
            "value_ratio_display": fmt_vr(r["value_ratio"]),
            "signal_label": signal_label,
            "signal_class": signal_class,
            "change_display": fmt_change(r["prev_signal"], signal_label),
            "prev_signal": r["prev_signal"] or "",
        })
    return out


def compute_changes(rows):
    """Identify upgrades and downgrades from prev_signal vs current signal_label."""
    order = ["Strong Sell", "Sell", "Fair Value", "Buy", "Strong Buy"]
    upgrades = []
    downgrades = []
    for r in rows:
        prev = r.get("prev_signal") or ""
        current = r.get("signal_label") or ""
        if not prev or not current or prev == current:
            continue
        try:
            prev_i = order.index(prev)
            curr_i = order.index(current)
        except ValueError:
            continue
        change = {
            "ticker": r["ticker"],
            "slug": r["slug"],
            "company": r["company"],
            "sector": r["sector"],
            "from_signal": prev,
            "to_signal": current,
            "to_signal_class": r["signal_class"],
            "is_held": r["is_held"],
            "value_ratio_display": r["value_ratio_display"],
        }
        if curr_i > prev_i:
            upgrades.append(change)
        else:
            downgrades.append(change)
    # Order both lists by company name for stable rendering
    upgrades.sort(key=lambda c: c["company"])
    downgrades.sort(key=lambda c: c["company"])
    return upgrades, downgrades


def latest_data_timestamp(records):
    stamps = [r.get("last_updated") for r in records if r.get("last_updated")]
    if not stamps: return "(unknown)"
    return max(stamps)


def is_financial_sector(sector):
    return sector in ("Banks", "General Insurance", "Life Insurance", "Asset Management",
                      "PE/Alternatives", "Capital Markets", "Financial Services")


def render_tracker(public_records, held_tickers, refreshed_at):
    rows = shape_for_tracker(public_records, held_tickers)
    rows.sort(key=lambda r: (r["sector"], r["ticker"]))
    sectors = sorted(set(r["sector"] for r in rows if r["sector"]))
    signal_counts = Counter(r["signal_label"] for r in rows)
    for sig in ("Strong Buy", "Buy", "Fair Value", "Sell", "Strong Sell"):
        signal_counts.setdefault(sig, 0)
    upgrades, downgrades = compute_changes(rows)
    held_count = sum(1 for r in rows if r["is_held"])

    body = env.get_template("tracker.html").render(
        rows=rows, sectors=sectors, signal_counts=signal_counts,
        ticker_count=len(rows), held_count=held_count,
        upgrades=upgrades, downgrades=downgrades, path_prefix="",
    )
    return env.get_template("_layout.html").render(
        page_title="FTSE Valuation Tracker",
        page_description=f"Three valuation models, one signal, {len(rows)} FTSE stocks, refreshed weekly.",
        canonical_path="/", active="tracker", path_prefix="",
        content=body, data_refreshed_at=refreshed_at,
    )


def render_ticker(r, refreshed_at, is_held):
    signal_label, signal_class = signal_for(r["value_ratio"])
    currency = r.get("currency", "")
    is_fin = is_financial_sector(r["sector"])

    if is_fin:
        val_dcf_display = "Not used"
        val_dcf_note = "DCF skipped for financial-sector stocks; sector-specific models used instead."
    else:
        val_dcf_display = fmt_target_smart(r["val_dcf"], currency, r["live_price"]) if r["val_dcf"] else "—"
        val_dcf_note = "5-year FCF projection plus terminal value, discounted at WACC."

    val_ddm_display = fmt_target_smart(r["val_ddm"], currency, r["live_price"]) if r["val_ddm"] else "—"
    val_ddm_note = ("Sector-weighted blend." if is_fin
                    else ("Gordon Growth: D₁ ÷ (WACC − g)." if r["val_ddm"]
                    else "No dividend or WACC ≤ g."))

    val_epv_display = fmt_target_smart(r["val_epv"], currency, r["live_price"]) if r["val_epv"] else "—"
    val_epv_note = "Forward EPS × normalised P/E, capped at 22.5×."

    if r["prev_signal"] and r["current_signal"] and r["prev_signal"] != r["current_signal"]:
        signal_change_html = f'Signal moved this week: <strong>{r["prev_signal"]}</strong> → <strong>{r["current_signal"]}</strong>'
    else:
        signal_change_html = ""

    body = env.get_template("ticker.html").render(
        ticker=r["ticker"], company=r["company"], sector=r["sector"],
        signal_label=signal_label, signal_class=signal_class,
        value_ratio_display=fmt_vr(r["value_ratio"]),
        price_display=fmt_price(r["live_price"], currency),
        target_display=fmt_target_smart(r["blended_target"], currency, r["live_price"]),
        signal_change_html=signal_change_html,
        is_held=is_held,
        val_dcf_display=val_dcf_display, val_dcf_note=val_dcf_note,
        val_ddm_display=val_ddm_display, val_ddm_note=val_ddm_note,
        val_epv_display=val_epv_display, val_epv_note=val_epv_note,
        model_method=r["model_method"] or "—",
        beta_display=f"{r['beta']:.3f}" if r["beta"] else "—",
        ke_or_wacc="Ke" if is_fin else "WACC",
        wacc_display=fmt_pct(r["wacc"], 2) if r["wacc"] else "—",
        g1_display=fmt_pct(r["g1"]) if r["g1"] else "5.00%",
        g2_display=fmt_pct(r["g2"]) if r["g2"] else "2.50%",
        data_refreshed_at=refreshed_at,
    )
    return env.get_template("_layout.html").render(
        page_title=f"{r['ticker']} — {r['company']} valuation",
        page_description=f"{r['company']} ({r['ticker']}). Three-model DCF/DDM/EPV blend, current signal {signal_label}, by Neil Daley, PhD, CFA.",
        canonical_path=f"/ticker/{slug_for(r['ticker'])}",
        active="", path_prefix="../", content=body, data_refreshed_at=refreshed_at,
    )


def render_methodology(methodology_source_path, refreshed_at):
    with open(methodology_source_path, encoding="utf-8") as f:
        full = f.read()
    m = re.search(r'<div class="wrap">(.*?)</div>\s*</body>', full, re.DOTALL)
    if m:
        inner = m.group(1)
    else:
        m2 = re.search(r'<body>(.*?)</body>', full, re.DOTALL)
        inner = m2.group(1) if m2 else "<p>Methodology content not found.</p>"
    body = f'<div class="prose-wrap">{inner}</div>'
    return env.get_template("_layout.html").render(
        page_title="Methodology",
        page_description="The three-model valuation framework behind Daley Valuations: DCF, DDM and EPV blended into a single fair-value target for 106 FTSE stocks.",
        canonical_path="/methodology", active="methodology", path_prefix="",
        content=body, data_refreshed_at=refreshed_at,
    )


def render_sitemap(public_records):
    base = "https://daleyvaluations.com"
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{base}/</loc><lastmod>{today}</lastmod><priority>1.0</priority></url>",
        f"  <url><loc>{base}/methodology</loc><lastmod>{today}</lastmod><priority>0.8</priority></url>",
    ]
    for r in public_records:
        slug = slug_for(r["ticker"])
        lines.append(f"  <url><loc>{base}/ticker/{slug}</loc><lastmod>{today}</lastmod><priority>0.6</priority></url>")
    lines.append("</urlset>")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_FILE)
    parser.add_argument("--portfolio", type=Path, default=DEFAULT_PORTFOLIO_FILE)
    parser.add_argument("--methodology-source", type=Path, default=REPO_ROOT / "methodology_source.html")
    parser.add_argument("--no-prices", action="store_true")
    parser.add_argument("--refresh-prices", action="store_true")
    args = parser.parse_args()

    print(f"[{datetime.now().isoformat()}] Building daleyvaluations.com")
    data = load_data(args.data)
    all_records = join_records(data)
    print(f"  Joined {len(all_records)} total records")
    public = filter_public(all_records)
    print(f"  Filtered to {len(public)} FTSE equities for public site")

    held_tickers = load_held_tickers(args.portfolio)

    if not args.no_prices:
        live_prices = fetch_live_prices(public, force_refresh=args.refresh_prices)
        public = apply_live_prices(public, live_prices)

    warnings = sanity_check(public)
    if warnings:
        print(f"  WARNINGS ({len(warnings)}):")
        for w in warnings: print(f"    - {w}")
    else:
        print(f"  Sanity check passed")

    refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M") + " (live)"

    tracker_html = render_tracker(public, held_tickers, refreshed_at)
    out_index = REPO_ROOT / ("index_preview.html" if args.preview else "index.html")
    with open(out_index, "w", encoding="utf-8") as f:
        f.write(tracker_html)
    print(f"  Wrote {out_index.name}")

    if args.methodology_source.exists():
        methodology_html = render_methodology(args.methodology_source, refreshed_at)
        with open(REPO_ROOT / "methodology.html", "w", encoding="utf-8") as f:
            f.write(methodology_html)
        print(f"  Wrote methodology.html")

    ticker_dir = REPO_ROOT / "ticker"
    ticker_dir.mkdir(exist_ok=True)
    count = 0
    for r in public:
        is_held = r["ticker"].upper() in held_tickers or r["yahoo_ticker"].upper() in held_tickers
        html = render_ticker(r, refreshed_at, is_held)
        out = ticker_dir / f"{slug_for(r['ticker'])}.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
    print(f"  Wrote {count} per-ticker pages to ticker/")

    if not args.preview:
        sitemap = render_sitemap(public)
        with open(REPO_ROOT / "sitemap.xml", "w", encoding="utf-8") as f:
            f.write(sitemap)
        print(f"  Wrote sitemap.xml")

    print(f"[{datetime.now().isoformat()}] Done")


if __name__ == "__main__":
    main()
