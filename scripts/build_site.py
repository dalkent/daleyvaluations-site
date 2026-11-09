#!/usr/bin/env python3
"""build_site.py - Daley Valuations site builder.

v3 (2026-11-09): every method statement on the site is derived from the model.
Component labels key on the method label, numbers are read from valuation.py and
signals.py, and the methodology page must carry the same version as the vault
Valuation Methodology doc or the build stops.
"""
import argparse, json, sys, time, os, shutil, re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"

# Canonical JSON sources. The local data\ folder is the working copy maintained
# by run_daily.py / eToro.bat / website.bat --revalue. The same files are also
# mirrored to C:\Users\Neil\My Drive\eToro Sync\ on every run, so the Mac and
# other consumers can read fresh data without a GitHub pull.
#
# To point this builder at a different copy (e.g. on Mac, or pinned to Drive),
# set ETORO_MASTER_JSON and ETORO_PORTFOLIO_JSON env vars.
DEFAULT_DATA_FILE = Path(
    os.environ.get(
        "ETORO_MASTER_JSON",
        "C:/Users/Neil/ClaudeCode/eToro/data/etoro_master.json",
    )
)
DEFAULT_PORTFOLIO_FILE = Path(
    os.environ.get(
        "ETORO_PORTFOLIO_JSON",
        "C:/Users/Neil/ClaudeCode/eToro/data/combined_portfolio.json",
    )
)
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


# The signal rule lives in ONE place: eToro/scripts/signals.py (2026-10-27).
# This repo sits beside the eToro folder (C:/Users/Neil/ClaudeCode/...); set
# ETORO_SCRIPTS_DIR to point elsewhere (e.g. on the Mac). No fallback copy on
# purpose: a silent local copy is exactly how the site drifted from the model.
ETORO_SCRIPTS_DIR = Path(os.environ.get("ETORO_SCRIPTS_DIR", REPO_ROOT.parent / "eToro" / "scripts"))


def _load_signals(path):
    """Load signals.py by exact file path, without touching sys.path (adding the
    eToro scripts dir to sys.path made importlib.reload(build_site) in the
    tracker pick up the eToro-side shim instead of this file)."""
    import importlib.util
    if "signals" in sys.modules:
        return sys.modules["signals"]
    p = Path(path) / "signals.py"
    if not p.exists():
        sys.exit(f"ERROR: signals.py not found in {path}. Set ETORO_SCRIPTS_DIR.")
    spec = importlib.util.spec_from_file_location("signals", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["signals"] = mod
    spec.loader.exec_module(mod)
    return mod


_signals = _load_signals(ETORO_SCRIPTS_DIR)


# ── Model constants, read from the model's own source (2026-11-09) ─────────
# The site never types a model number by hand. Everything the methodology page
# and the ticker pages quote comes from valuation.py / signals.py at build time.
def _load_model_constants(scripts_dir):
    import ast
    src_path = Path(scripts_dir) / "valuation.py"
    if not src_path.exists():
        sys.exit(f"ERROR: valuation.py not found in {scripts_dir}. Set ETORO_SCRIPTS_DIR.")
    src = src_path.read_text(encoding="utf-8")
    out = {}
    for node in ast.parse(src).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper()):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except Exception:
                pass
    # Values written inline in valuation.py rather than as named constants.
    # Each is checked against the source so a code change stops the build.
    inline = {
        "BETA_FLOOR_DEFAULT":   (0.5,  r'SECTOR_BETA_FLOOR\.get\(sector or "", 0\.5\)'),
        "BETA_CAP":             (2.5,  r"min\(beta or 1\.0, 2\.5\)"),
        "BETA_MISSING":         (1.0,  r"min\(beta or 1\.0, 2\.5\)"),
        "CEV_DISCOUNT":         (0.05, r"discount_pct: float = 0\.05"),
        "PE_ALT_BOOK_MULTIPLE": (1.10, r"val = book \* 1\.10"),
        "WINSOR_FACTOR":        (3,    r"upper, lower = med \* 3, med / 3"),
        "YIELD_DCF_CAP":        (2,    r"if dcf_v > 2 \* anchor_max"),
        "PB_CLAMP_LOW":         (0.3,  r"max\(0\.3, min\(3\.0, 1 \+ \(roe - ke\) / \(ke - g\)\)\)"),
        "PB_CLAMP_HIGH":        (3.0,  r"max\(0\.3, min\(3\.0, 1 \+ \(roe - ke\) / \(ke - g\)\)\)"),
        "DIV_CROSSCHECK":       (1.25, r"min\(_from_yield, _from_trail\) > 1\.25"),
    }
    for name, (val, pattern) in inline.items():
        if not re.search(pattern, src):
            sys.exit(f"ERROR: build_site.py expects {name}={val} in valuation.py "
                     f"(pattern {pattern!r} not found). Update the site to match the model.")
        out[name] = val
    for name in ("STRONG_BUY", "BUY", "FAIR", "SELL", "EPS_GUARD_LOW", "EPS_GUARD_HIGH",
                 "EPS_GUARD_BAND", "INVESTIGATE_BANDS"):
        out[name] = getattr(_signals, name)
    required = ("GROWTH_5Y", "TERMINAL_GROWTH", "PE_MULTIPLE", "RF_UK", "RF_US", "ERP",
                "SECTOR_BETA_FLOOR", "FCF_CONVERSION", "SKIP_DDM_SECTORS",
                "SKIP_FALLBACK_DCF_SECTORS", "NONFIN_ARCHETYPE_WEIGHTS",
                "SECTOR_DEFAULT_ARCHETYPE", "FIN_BLEND_WEIGHTS", "BANK_EM_PREMIUM",
                "CM_EV_EBITDA")
    missing = [k for k in required if k not in out]
    if missing:
        sys.exit(f"ERROR: constants missing from valuation.py: {missing}")
    return out


MODEL = _load_model_constants(ETORO_SCRIPTS_DIR)


# ── Methodology version check (2026-11-09) ─────────────────────────────────
# The methodology page states the vault doc version it matches. If the vault
# doc has moved on, the build stops, so the site cannot fall behind the model.
def _methodology_doc_path():
    if os.environ.get("METHODOLOGY_DOC"):
        return Path(os.environ["METHODOLOGY_DOC"])
    rel = Path("Daley's Brain") / "Projects" / "eToro & Investing" / "Reference" / \
        "Valuation Methodology" / "Valuation Methodology.md"
    home = Path.home()
    for drive in (home / "My Drive",
                  home / "Library" / "CloudStorage" / "GoogleDrive-ndaley1313@gmail.com" / "My Drive",
                  home / "Google Drive" / "My Drive"):
        if (drive / rel).exists():
            return drive / rel
    return home / "My Drive" / rel


def methodology_doc_version():
    p = _methodology_doc_path()
    if not p.exists():
        sys.exit(f"ERROR: methodology doc not found at {p}. Set METHODOLOGY_DOC.")
    m = re.search(r"^version:\s*([0-9.]+)\s*$", p.read_text(encoding="utf-8"), re.MULTILINE)
    if not m:
        sys.exit(f"ERROR: no 'version:' line in {p}")
    return m.group(1)


def check_methodology_version(source_text):
    """Return the version stamped on the page; stop the build on a mismatch."""
    m = re.search(r'data-methodology-version="([0-9.]+)"', source_text)
    page_v = m.group(1) if m else None
    doc_v = methodology_doc_version()
    if page_v != doc_v:
        sys.exit(f"ERROR: methodology page is stamped v{page_v} but the vault doc is v{doc_v}. "
                 f"Update methodology_source.html to match the doc, then change its stamp.")
    return doc_v

SUBSTACK_URL = "https://daleyvaluations.substack.com"

_CLASS = {"Strong Buy": "sb", "Buy": "b", "Fair Value": "fv", "Sell": "s", "Strong Sell": "ss", "N/A": "na"}


def is_single_source(method):
    return _signals.is_single_source(method)


def signal_for(vr, method=None):
    """(label, css_class) for the published signal. Rule lives in signals.py."""
    label = _signals.signal(vr, method)
    return label, _CLASS[label]


def source_marker(method):
    """(tag, tooltip) for thin valuations, or (None, None). Shown beside the signal."""
    m = str(method or "")
    if m.startswith("Analyst Consensus"):
        return "Consensus", "Target is the analyst consensus, not my model. Treat the signal with caution."
    if _signals.is_single_source(m):
        return "1 model", "Target rests on a single valuation method, so it has not been cross-checked. Treat the signal with caution."
    return None, None


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


def change_rank(prev, current):
    """Numeric delta in signal rank: positive = upgrade, negative = downgrade, 0 = flat."""
    if not prev or not current or prev == current:
        return 0
    order = ["Strong Sell", "Sell", "Fair Value", "Buy", "Strong Buy"]
    try:
        return order.index(current) - order.index(prev)
    except ValueError:
        return 0


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
            "forward_target": to_float(v.get("Forward Target")),   # recovery case (2026-10-27)
            "forward_signal_model": v.get("Forward Signal") or "",
            "investigate_model": v.get("Investigate") or "",
            "implied_growth": to_float(v.get("Implied 5yr Growth")),
            "market_expectation": v.get("Market Expectation") or "",
            "model_method": v.get("Model / Method") or "",
            "last_updated": v.get("Last Updated", ""),
            "prev_signal": v.get("Prev Signal", ""),
            "current_signal": v.get("Current Signal", ""),
            "live_price": to_float(watch.get("Live Price (Local) ¹")),
            "value_ratio": to_float(watch.get("Value Ratio")),
        })
    return merged


# Tickers excluded from the public site (decision D2, 9 Nov 2026).
# Both run on the closed-end method (NAV x (1 - CEV_DISCOUNT)), but a flat 5%
# discount misleads for these two:
# - PSH.L trades around 40% below NAV, so the method shows a Strong Buy every week.
# - III.L usually trades near or above NAV, so it would show a structural Sell.
# Revisit when the closed-end method uses each trust's own average discount.
# The methodology page states this exclusion.
EXCLUDED_TICKERS = {"PSH.L", "III.L"}


# Blend overrides were removed on 9 Nov 2026: the site only ever shows the
# model's own target. blend_overrides.json is no longer read.

# A valuation older than this is not published (BEZ.L and SDR.L sat on retired
# models from 10 Oct 2026 because Yahoo stopped returning their prices).
STALE_DAYS = 7


def _parse_stamp(v):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except (TypeError, ValueError):
            continue
    return None


def is_stale(r, now=None):
    ts = _parse_stamp(r.get("last_updated"))
    if ts is None:
        return True
    return ((now or datetime.now()) - ts).days > STALE_DAYS


def filter_public(records):
    return [r for r in records
            if r.get("market") == "FTSE"
            and r.get("asset_type") == "Equity"
            and r.get("sector") != "Corp Bonds"
            and r.get("current_signal")
            and (r.get("model_method") or "").strip().lower() != "no valuation"
            and r.get("ticker") not in EXCLUDED_TICKERS
            and not is_stale(r)]


def stale_public_candidates(records):
    """Tickers that would be public but are dropped as stale (for the build log)."""
    return [r["ticker"] for r in records
            if r.get("market") == "FTSE" and r.get("asset_type") == "Equity"
            and r.get("current_signal") and r.get("ticker") not in EXCLUDED_TICKERS
            and is_stale(r)]


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
        signal_label, signal_class = signal_for(r["value_ratio"], r.get("model_method"))
        marker, marker_note = source_marker(r.get("model_method"))
        currency = r.get("currency", "")
        is_held = r["ticker"].upper() in held_tickers or r["yahoo_ticker"].upper() in held_tickers
        flags = table_flags(caution_flags(r, signal_label), signal_label)
        out.append({
            "marker": marker,
            "marker_note": marker_note,
            "flag_tag": "Caution" if flags else "",
            "flag_note": " ".join(f"{t}: {n}" for t, n in flags),
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
            "change_rank": change_rank(r["prev_signal"], signal_label),
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


def render_tracker(public_records, held_tickers, refreshed_at, cache_bust="", change_label="since the last refresh"):
    rows = shape_for_tracker(public_records, held_tickers)
    rows.sort(key=lambda r: (r["sector"], r["ticker"]))
    sectors = sorted(set(r["sector"] for r in rows if r["sector"]))
    signal_counts = Counter(r["signal_label"] for r in rows)
    for sig in ("Strong Buy", "Buy", "Fair Value", "Sell", "Strong Sell"):
        signal_counts.setdefault(sig, 0)
    upgrades, downgrades = compute_changes(rows)
    held_count = sum(1 for r in rows if r["is_held"])

    # Top 5 / Bottom 5 by DVR (only rows with a real ratio)
    rated = [r for r in rows if r.get("value_ratio_raw")]
    rated_sorted = sorted(rated, key=lambda r: r["value_ratio_raw"], reverse=True)
    top_cheap = rated_sorted[:5]
    top_expensive = list(reversed(rated_sorted[-5:]))

    # Sector summary - filter to sectors with 2+ rated names, take 3 cheapest + 3 most expensive
    all_sectors = []
    for sec in sectors:
        secrows = [r for r in rated if r["sector"] == sec]
        if len(secrows) < 2: continue
        avg_dvr_num = sum(r["value_ratio_raw"] for r in secrows) / len(secrows)
        _band = _signals.raw_signal(avg_dvr_num)   # thresholds from signals.py
        tint = "buy" if _band in ("Strong Buy", "Buy") else "fair" if _band == "Fair Value" else "sell"
        all_sectors.append({
            "sector": sec,
            "count": len(secrows),
            "avg_dvr_num": avg_dvr_num,
            "avg_dvr": f"{avg_dvr_num:.2f}",
            "tint": tint,
        })
    all_sectors.sort(key=lambda s: s["avg_dvr_num"], reverse=True)
    cheap_sectors = all_sectors[:3]
    expensive_sectors = list(reversed(all_sectors[-3:]))

    body = env.get_template("tracker.html").render(
        rows=rows, sectors=sectors, signal_counts=signal_counts,
        ticker_count=len(rows), held_count=held_count,
        upgrades=upgrades, downgrades=downgrades,
        top_cheap=top_cheap, top_expensive=top_expensive,
        cheap_sectors=cheap_sectors, expensive_sectors=expensive_sectors,
        change_label=change_label, path_prefix="",
    )
    return env.get_template("_layout.html").render(
        page_title="FTSE Valuation Tracker",
        page_description=f"Three valuation models, one signal, {len(rows)} FTSE stocks, refreshed weekly.",
        canonical_path="/", active="tracker", path_prefix="",
        content=body, data_refreshed_at=refreshed_at, cache_bust=cache_bust,
        substack_url=SUBSTACK_URL,
    )


# ── Component labels, keyed on the model's method label (2026-11-09) ────────
# The JSON has three value slots (Assumptions cols I, J, K). What each slot holds
# depends on the method, so labels key on the method label, never the sector.
# A method prefix not listed here stops the build: a model change must not
# silently mislabel pages again (the April labels did this to every Fin: page).
def _pct(x, d=1):
    return f"{x * 100:.{d}f}%".replace(".0%", "%")


def _num(x):
    return f"{x:g}"


def _slot(key, comp, label, note):
    return {"key": key, "comp": comp, "label": label, "note": note}


def component_slots(method, sector=""):
    """[slot1, slot2, slot3] for the three JSON value fields, or exit on an unknown method."""
    m = str(method or "")
    g2 = _pct(MODEL["TERMINAL_GROWTH"])
    pe = _num(MODEL["PE_MULTIPLE"])
    unused = lambda k: _slot(k, None, "Not used", "Not part of this method.")
    nonfin = [
        _slot("val_dcf", "dcf", "DCF",
              f"Free cash flow to shareholders (3-year average), grown {_pct(MODEL['GROWTH_5Y'])} a year for five years "
              f"then {g2} for ever, discounted at WACC."),
        _slot("val_ddm", "ddm", "DDM", f"Dividend × (1 + {g2}) ÷ (WACC − {g2})."),
        _slot("val_epv", "epv", "EPV",
              f"Earnings per share × {pe}. Dropped if trailing earnings are zero or negative, or if forward and "
              f"trailing earnings are more than {_num(MODEL['EPS_GUARD_HIGH'])}x apart."),
    ]
    if m.startswith(("Archetype:", "primary", "fallback", "skip")):
        return nonfin
    if m.startswith("Fin:Bank"):
        return [
            _slot("val_dcf", "book", "Book value",
                  f"Book value × justified price-to-book: 1 + (ROE − Ke) ÷ (Ke − {g2}), held between "
                  f"{_num(MODEL['PB_CLAMP_LOW'])}x and {_num(MODEL['PB_CLAMP_HIGH'])}x."),
            _slot("val_ddm", "ddm", "DDM", f"Cash dividend × (1 + {g2}) ÷ (Ke − {g2}). Buybacks excluded."),
            _slot("val_epv", "ern", "Earnings", "Earnings per share ÷ Ke."),
        ]
    if m.startswith(("Fin:GI", "Fin:Life", "Fin:AM")):
        return [
            _slot("val_dcf", None, "Book value", "Not used for insurers and asset managers: book value understates what they own."),
            _slot("val_ddm", "ddm", "DDM", f"Cash dividend × (1 + {g2}) ÷ (Ke − {g2}). Buybacks excluded."),
            _slot("val_epv", "ern", "Earnings", "Earnings per share ÷ Ke."),
        ]
    if m.startswith("Fin:DDM+EPV+RIM"):
        return [
            unused("val_dcf"),
            _slot("val_ddm", "ddm", "DDM", f"Dividend × (1 + {g2}) ÷ (Ke − {g2})."),
            _slot("val_epv", "ern", "Earnings", "Trailing earnings per share ÷ Ke."),
        ]
    if m.startswith("CEV:"):
        return [
            unused("val_dcf"),
            _slot("val_ddm", None, "NAV per share", "Balance-sheet equity ÷ shares outstanding."),
            _slot("val_epv", None, "Target",
                  f"NAV less a {_pct(MODEL['CEV_DISCOUNT'])} discount."),
        ]
    if m.startswith("CM:"):
        return [unused("val_dcf"), unused("val_ddm"),
                _slot("val_epv", None, "EV / EBITDA",
                      f"(EBITDA × {_num(MODEL['CM_EV_EBITDA'])} − net debt) ÷ shares.")]
    if m.startswith("PE:"):
        return [unused("val_dcf"), unused("val_ddm"),
                _slot("val_epv", None, "Book value",
                      f"Book value × {_num(MODEL['PE_ALT_BOOK_MULTIPLE'])}.")]
    if m.startswith("Analyst Consensus"):
        if is_financial_sector(sector):
            return [
                _slot("val_dcf", None, "Book value", "Not available for this stock."),
                _slot("val_ddm", None, "DDM", "Not available for this stock."),
                _slot("val_epv", None, "Earnings", "Not available for this stock."),
            ]
        return nonfin
    sys.exit(f"ERROR: unknown method label {m!r}. Add it to component_slots() in build_site.py.")


ARCHETYPE_TEXT = {
    "Mature compounder": "steady, cash-generative businesses",
    "Mature cyclical": "businesses whose earnings move with the economy",
    "Yield anchor": "businesses valued mainly on their dividend",
    "Capex cyclical": "capital-heavy, commodity-linked businesses",
    "Restructuring": "businesses in transition",
}
FIN_TEXT = {"Bank": "Bank blend", "GI": "General insurer blend", "Life": "Life insurer blend",
            "AM": "Asset manager blend"}
COMP_NAME = {"dcf": "DCF", "ddm": "DDM", "epv": "EPV", "book": "Book", "ern": "Earnings"}


def method_plain(method):
    """Plain-English description of the method label."""
    m = str(method or "")
    w = _signals._blend_weights(m)
    order = ["book", "dcf", "ddm", "epv", "ern"]
    weights = " · ".join(f"{COMP_NAME.get(k, k.upper())} {w[k]:g}%"
                         for k in sorted(w, key=lambda k: order.index(k) if k in order else 9))
    if m.startswith("Archetype:"):
        name = m.split(":", 1)[1].split("(")[0]
        src = " (sector default)" if "[sector-default]" in m else ""
        text = f"{name} archetype{src}, for {ARCHETYPE_TEXT.get(name, 'this business type')}"
        if "+DCFcap2x" in m:
            text += f". DCF capped at {MODEL['YIELD_DCF_CAP']}x the higher of DDM and EPV"
        return text, weights
    if m.startswith("Fin:DDM+EPV+RIM"):
        return "Financial services blend, equal weight", ""
    if m.startswith("Fin:"):
        short = m.split(":", 1)[1].split("(")[0]
        text = FIN_TEXT.get(short, "Financial blend")
        if "+Analyst" in m:
            text += ", analyst consensus used because no component survived"
        return text, weights
    if m.startswith("CEV:"):
        return f"Closed-end vehicle: NAV less {_pct(MODEL['CEV_DISCOUNT'])}", ""
    if m.startswith("CM:"):
        return f"Capital markets: {_num(MODEL['CM_EV_EBITDA'])}x EV/EBITDA", ""
    if m.startswith("PE:"):
        return f"Private equity / alternatives: book × {_num(MODEL['PE_ALT_BOOK_MULTIPLE'])}", ""
    if m.startswith("Analyst Consensus"):
        return "Analyst consensus: no model component survived for this stock", ""
    if m.startswith(("primary", "fallback", "skip")):
        return (f"Equal-weight blend, each component held within {MODEL['WINSOR_FACTOR']}x of the median", "")
    return m or "—", ""


EXPECTATION_TEXT = {
    "Prices ~no growth": "the market is pricing in almost no growth",
    "Cheap vs expectations": "cheap against the model's growth",
    "In line": "in line with the model",
    "Demanding": "a demanding expectation",
    "Priced for perfection": "priced for perfection",
}


def applied_beta(beta, sector, is_fin):
    """Beta after the model's floor and cap (WACC uses the sector floor, Ke does not)."""
    floor = MODEL["BETA_FLOOR_DEFAULT"] if is_fin else MODEL["SECTOR_BETA_FLOOR"].get(sector or "", MODEL["BETA_FLOOR_DEFAULT"])
    b = MODEL["BETA_MISSING"] if beta is None else beta
    return max(floor, min(b, MODEL["BETA_CAP"]))


def missing_reason(slot, r):
    """Why a model component has no value on this stock."""
    sector = r.get("sector") or ""
    comp = slot["comp"]
    if comp == "ddm" and sector in MODEL["SKIP_DDM_SECTORS"]:
        return "Excluded for this sector"
    if comp == "dcf" and sector in MODEL["SKIP_FALLBACK_DCF_SECTORS"]:
        return "Not usable: needs three positive cash-flow years"
    if comp in ("epv", "ern", "book") and r.get("forward_target") and r.get("blended_target") \
            and abs(r["forward_target"] - r["blended_target"]) > 1e-9:
        return "Dropped: earnings check"
    if comp == "ddm":
        return "No dividend"
    return "No data"


# ── Caution tags (decision D1, 9 Nov 2026) ─────────────────────────────────
# Same rules as signals.investigate_reasons(), recomputed at the site's live
# value ratio, then put into plain English. "1 model" and "Consensus" keep
# their own marker. The actionable Investigate list stays private.
_HINGE_NAME = {"DCF": "the cash flow model", "DDM": "the dividend model", "EPV": "the earnings model",
               "BOOK": "the book value model", "ERN": "the earnings model"}


def ratio_for(target, r):
    """Value ratio for a target on this record, same unit logic as apply_live_prices()."""
    live = r.get("live_price")
    if target is None or not live or live <= 0:
        return None
    if r.get("currency", "") in ("GBp", "GBX"):
        dec, pen = (target * 100) / live, target / live
        if 0.2 <= dec <= 5.0: return dec
        if 0.2 <= pen <= 5.0: return pen
        return dec
    return target / live


def forward_signal_site(r, site_signal):
    ft = r.get("forward_target")
    if not ft or (r.get("blended_target") and abs(ft - r["blended_target"]) < 1e-9):
        return site_signal
    return _signals.raw_signal(ratio_for(ft, r))


def _components(r):
    m = str(r.get("model_method") or "")
    keys = ("book", "ddm", "ern") if m.startswith("Fin:") else ("dcf", "ddm", "epv")
    return dict(zip(keys, (r.get("val_dcf"), r.get("val_ddm"), r.get("val_epv"))))


def caution_flags(r, site_signal):
    """[(tag, explanation)] for this record."""
    fwd = forward_signal_site(r, site_signal)
    m = re.search(r"EPS near guard \(([0-9.]+)x\)", r.get("investigate_model") or "")
    eps_ratio = float(m.group(1)) if m else None
    if str(r.get("model_method") or "").startswith(("CEV:", "CM:", "PE:")):
        eps_ratio = None   # earnings do not feed these targets
    reasons = _signals.investigate_reasons(site_signal, fwd, r.get("model_method"), _components(r),
                                           r.get("value_ratio"), eps_ratio=eps_ratio)
    out = []
    for reason in reasons:
        if reason in ("1 model", "consensus target"):
            continue
        if reason.startswith("forward view"):
            out.append(("Forward view differs",
                        f"If consensus earnings arrive, the same model gives {fwd}."))
        elif reason.startswith("hinges on"):
            key = reason.split()[-1]
            name = _HINGE_NAME.get(key, "one model")
            out.append((f"Rests on {COMP_NAME.get(key.lower(), key)}",
                        f"Removing {name} alone would move this stock out of {site_signal}."))
        elif reason.startswith("EPS near guard"):
            edge = MODEL["EPS_GUARD_HIGH"] if eps_ratio >= 1 else MODEL["EPS_GUARD_LOW"]
            out.append(("Earnings check borderline",
                        f"Forward earnings are {eps_ratio:.2f}x trailing, close to the {_num(edge)}x limit where "
                        f"the earnings model is dropped. A small change in forecasts could move the signal."))
    return out


def table_flags(flags, site_signal):
    """Tracker-table subset (9 Nov 2026): only signals that could flip on a small
    change. 'Rests on X' shows on the table only for a Strong Buy; for a Strong
    Sell it usually means a small dividend, i.e. the strict lens, not fragility.
    Ticker pages show every reason."""
    keep = []
    for tag, note in flags:
        if tag in ("Earnings check borderline", "Forward view differs"):
            keep.append((tag, note))
        elif tag.startswith("Rests on") and site_signal == "Strong Buy":
            keep.append((tag, note))
    return keep


def load_baseline_signals(data_file, days=7):
    """Model signals from the most recent backup at least `days` old.
    Returns ({ticker: signal}, timestamp) or ({}, None) if no backup qualifies."""
    bdir = Path(data_file).parent / "backups"
    if not bdir.exists():
        return {}, None
    cutoff = datetime.now() - timedelta(days=days)
    best = None
    for f in bdir.glob("etoro_master.*.json"):
        mt = re.match(r"etoro_master\.(\d{4}-\d{2}-\d{2}-\d{4})\.json$", f.name)
        if not mt:
            continue
        ts = datetime.strptime(mt.group(1), "%Y-%m-%d-%H%M")
        if ts <= cutoff and (best is None or ts > best[0]):
            best = (ts, f)
    if not best:
        return {}, None
    try:
        with open(best[1], encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        print(f"  WARNING: baseline {best[1].name} unreadable ({e}) - using previous-run signals")
        return {}, None
    sig = {(v.get("Ticker") or "").strip(): v.get("Current Signal") or ""
           for v in get_records(data, ("assumptions", "valuations"))}
    return sig, best[0]


def fmt_day(ts):
    return f"{ts.day} {ts:%b %Y}"


def render_ticker(r, refreshed_at, is_held, cache_bust="", change_label="since the last refresh"):
    signal_label, signal_class = signal_for(r["value_ratio"], r.get("model_method"))
    marker, marker_note = source_marker(r.get("model_method"))
    currency = r.get("currency", "")
    method = r.get("model_method", "")
    is_fin = str(method).startswith(("Fin:", "CEV:", "CM:", "PE:")) or is_financial_sector(r["sector"])

    weights = _signals._blend_weights(method)
    models = []
    for slot in component_slots(method, r.get("sector", "")):
        v = r.get(slot["key"])
        if slot["label"] == "Not used":
            continue
        if slot["comp"] is None and slot["note"].startswith("Not "):
            display, weight = "Not used", ""
        elif v:
            display = fmt_target_smart(v, currency, r["live_price"])
            weight = f"{weights[slot['comp']]:g}%" if slot["comp"] in weights else ""
        else:
            display, weight = missing_reason(slot, r), ""
        models.append({"label": slot["label"], "display": display, "weight": weight, "note": slot["note"]})

    method_text, weights_text = method_plain(method)

    fwd = forward_signal_site(r, signal_label)
    forward_line = (f"If consensus earnings arrive: {fwd} "
                    f"(target {fmt_target_smart(r['forward_target'], currency, r['live_price'])})"
                    if fwd != signal_label and r.get("forward_target") else "")

    implied = ""
    if r.get("implied_growth") is not None and not is_fin:
        expect = EXPECTATION_TEXT.get(r.get("market_expectation") or "", "")
        implied = (f"Today's price assumes free cash flow grows {r['implied_growth'] * 100:.1f}% a year for five years, "
                   f"against the model's {_pct(MODEL['GROWTH_5Y'])}"
                   + (f": {expect}." if expect else "."))

    beta = r.get("beta")
    applied = applied_beta(beta, r.get("sector", ""), is_fin)
    beta_text = (f"{beta:.3f}" if beta is not None else "—")
    if beta is not None and abs(applied - beta) > 0.0005:
        beta_text = f"{beta:.3f} measured, {applied:.2f} applied"
    elif beta is None:
        beta_text = f"Not available, {applied:.2f} applied"
    m_ = str(method)
    if m_.startswith("CEV:"):
        assumptions = [("Discount to NAV", _pct(MODEL["CEV_DISCOUNT"]))]
    elif m_.startswith("CM:"):
        assumptions = [("EV / EBITDA multiple", f"{_num(MODEL['CM_EV_EBITDA'])}x")]
    elif m_.startswith("PE:"):
        assumptions = [("Book multiple", f"{_num(MODEL['PE_ALT_BOOK_MULTIPLE'])}x")]
    elif is_fin:
        assumptions = [
            ("Beta", beta_text),
            ("Cost of equity (Ke)", fmt_pct(r["wacc"], 2) if r["wacc"] else "—"),
            ("Dividend growth (DDM)", _pct(MODEL["TERMINAL_GROWTH"])),
        ]
    else:
        assumptions = [
            ("Beta", beta_text),
            ("Cost of capital (WACC)", fmt_pct(r["wacc"], 2) if r["wacc"] else "—"),
            ("Five-year growth (DCF)", _pct(r["g1"]) if r["g1"] else _pct(MODEL["GROWTH_5Y"])),
            ("Long-run growth (DCF, DDM)", _pct(r["g2"]) if r["g2"] else _pct(MODEL["TERMINAL_GROWTH"])),
            ("Earnings multiple (EPV)", f"{_num(MODEL['PE_MULTIPLE'])}x"),
        ]

    if r["prev_signal"] and signal_label and r["prev_signal"] != signal_label:
        signal_change_html = (f'Signal moved {change_label}: <strong>{r["prev_signal"]}</strong> → '
                              f'<strong>{signal_label}</strong>')
    else:
        signal_change_html = ""

    body = env.get_template("ticker.html").render(
        ticker=r["ticker"], company=r["company"], sector=r["sector"],
        signal_label=signal_label, signal_class=signal_class,
        marker=marker, marker_note=marker_note,
        flags=caution_flags(r, signal_label),
        value_ratio_display=fmt_vr(r["value_ratio"]),
        price_display=fmt_price(r["live_price"], currency),
        target_display=fmt_target_smart(r["blended_target"], currency, r["live_price"]),
        signal_change_html=signal_change_html,
        is_held=is_held,
        models=models, method_text=method_text, weights_text=weights_text,
        forward_line=forward_line, implied=implied, assumptions=assumptions,
        substack_url=SUBSTACK_URL,
        data_refreshed_at=refreshed_at,
    )
    return env.get_template("_layout.html").render(
        page_title=f"{r['ticker']} — {r['company']} valuation",
        page_description=f"{r['company']} ({r['ticker']}). Systematic valuation, current signal {signal_label}, by Neil Daley, PhD, CFA.",
        canonical_path=f"/ticker/{slug_for(r['ticker'])}",
        active="", path_prefix="../", content=body, data_refreshed_at=refreshed_at, cache_bust=cache_bust,
        substack_url=SUBSTACK_URL,
    )


def methodology_context(public_count):
    """Numbers quoted on the methodology page, all read from the model."""
    M = MODEL
    arche = [(name, {k: round(v * 100) for k, v in w.items()}) for name, w in M["NONFIN_ARCHETYPE_WEIGHTS"].items()]
    defaults = {}
    for sec, arch in M["SECTOR_DEFAULT_ARCHETYPE"].items():
        defaults.setdefault(arch, []).append(sec)
    fin = [(sub, {k: round(v * 100) for k, v in w.items()}) for sub, w in M["FIN_BLEND_WEIGHTS"].items()]
    floor = sorted(M["SECTOR_BETA_FLOOR"].items())
    return {
        "M": M, "pct": _pct, "num": _num, "count": public_count,
        "archetypes": arche, "defaults": defaults, "fin_weights": fin,
        "fcf_conversion": sorted(M["FCF_CONVERSION"].items(), key=lambda kv: -kv[1]),
        "beta_floor_sectors": " and ".join(s for s, _ in floor),
        "beta_floor": _num(floor[0][1]) if floor else "",
        "em_premium": _pct(max(M["BANK_EM_PREMIUM"].values())) if M["BANK_EM_PREMIUM"] else "",
        "excluded": sorted(EXCLUDED_TICKERS),
        "stale_days": STALE_DAYS,
    }


def render_methodology(methodology_source_path, refreshed_at, cache_bust="", public_count=0):
    with open(methodology_source_path, encoding="utf-8") as f:
        src = f.read()
    version = check_methodology_version(src)
    inner = env.from_string(src).render(**methodology_context(public_count), version=version)
    body = f'<div class="prose-wrap">{inner}</div>'
    return env.get_template("_layout.html").render(
        page_title="Methodology",
        page_description=f"How Daley Valuations values {public_count} FTSE stocks: DCF, DDM and earnings models, "
                         f"blended by business type, with every rule and number written down.",
        canonical_path="/methodology", active="methodology", path_prefix="",
        content=body, data_refreshed_at=refreshed_at, cache_bust=cache_bust,
        substack_url=SUBSTACK_URL,
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

    stale = stale_public_candidates(all_records)
    if stale:
        print(f"  WARNING: not published, valuation older than {STALE_DAYS} days: {', '.join(stale)}")

    held_tickers = load_held_tickers(args.portfolio)

    baseline, baseline_ts = load_baseline_signals(args.data)
    if baseline_ts:
        change_label = f"since {fmt_day(baseline_ts)}"
        for r in public:
            r["prev_signal"] = baseline.get(r["ticker"], "")
        print(f"  Signal changes measured against the {baseline_ts:%Y-%m-%d %H:%M} backup")
    else:
        change_label = "since the last refresh"
        print("  WARNING: no backup 7+ days old - signal changes use the previous run")

    if not args.no_prices:
        live_prices = fetch_live_prices(public, force_refresh=args.refresh_prices)
        public = apply_live_prices(public, live_prices)

    warnings = sanity_check(public)
    if warnings:
        print(f"  WARNINGS ({len(warnings)}):")
        for w in warnings: print(f"    - {w}")
    else:
        print(f"  Sanity check passed")

    cache_bust = str(int(datetime.now().timestamp()))
    refreshed_at = datetime.now().strftime("%Y-%m-%d %H:%M") + " (live)"

    tracker_html = render_tracker(public, held_tickers, refreshed_at, cache_bust, change_label)
    out_index = REPO_ROOT / ("index_preview.html" if args.preview else "index.html")
    with open(out_index, "w", encoding="utf-8") as f:
        f.write(tracker_html)
    print(f"  Wrote {out_index.name}")

    if not args.methodology_source.exists():
        sys.exit(f"ERROR: {args.methodology_source} not found")
    if True:
        methodology_html = render_methodology(args.methodology_source, refreshed_at, cache_bust, len(public))
        with open(REPO_ROOT / "methodology.html", "w", encoding="utf-8") as f:
            f.write(methodology_html)
        print(f"  Wrote methodology.html")

    ticker_dir = REPO_ROOT / "ticker"
    ticker_dir.mkdir(exist_ok=True)
    count = 0
    for r in public:
        is_held = r["ticker"].upper() in held_tickers or r["yahoo_ticker"].upper() in held_tickers
        html = render_ticker(r, refreshed_at, is_held, cache_bust, change_label)
        out = ticker_dir / f"{slug_for(r['ticker'])}.html"
        with open(out, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
    print(f"  Wrote {count} per-ticker pages to ticker/")

    # Remove pages for tickers no longer published (stale, excluded or dropped),
    # so an old signal cannot stay reachable by URL.
    keep = {f"{slug_for(r['ticker'])}.html" for r in public}
    for old_page in sorted(ticker_dir.glob("*.html")):
        if old_page.name not in keep:
            try:
                old_page.unlink()
                print(f"  Removed unpublished page ticker/{old_page.name}")
            except OSError as e:
                print(f"  WARNING: could not remove ticker/{old_page.name} ({e})")

    if not args.preview:
        sitemap = render_sitemap(public)
        with open(REPO_ROOT / "sitemap.xml", "w", encoding="utf-8") as f:
            f.write(sitemap)
        print(f"  Wrote sitemap.xml")

    print(f"[{datetime.now().isoformat()}] Done")


if __name__ == "__main__":
    main()
