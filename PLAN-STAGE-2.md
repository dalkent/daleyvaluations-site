# daleyvaluations.com - Stage 2 Plan

> Written 2026-04-29. Adds the live valuation tracker and per-ticker pages to the site that currently only hosts the methodology page.

## What we are building

A public version of the work you do every week. Three connected things:

1. **Homepage = the live FTSE Valuation Tracker.** All 114 stocks in one sortable, filterable table. Refreshed weekly. The thing readers come back for.
2. **Per-ticker pages** at `/lloy-l`, `/gsk-l`, etc. Each page is the public face of one stock: current price, blended target, three model outputs, signal history, and links to every Substack article that covers it.
3. **Methodology page** moves from `/` to `/methodology`. The current single-page site becomes one section of a larger, but still small, research site.

What this is NOT:
- Not a blog (Substack stays the home of articles)
- Not a real-time tickertape (data refreshes weekly with the tracker, not by the second)
- Not a stock-screener product (no advanced filters, charting, or alerts; this is a research site, not a tool)
- Not paywalled at this stage (free-only stance until 200 Substack subscribers)

## Why this is genuinely worth building

The site stops being a calling card and becomes a research product the moment the tracker goes live. Three reasons:

1. **It is the only credible UK retail research site with weekly DCF/DDM/EPV outputs on 114 names.** Nothing like it exists at this price point (free).
2. **Per-ticker pages compound for SEO over time.** "Lloyds DCF valuation 2026" is a search query Google currently has weak answers for. Once you have a `/lloy-l` page indexed, it becomes a sustained traffic source. 114 indexed pages, each refreshed weekly, is genuine SEO compound.
3. **It changes the X-to-Substack-to-eToro funnel.** A `daleyvaluations.com/lloy-l` link reads as a resource, not a sales pitch. Easier to share, easier to land.

## The architecture

Two principles drive every technical decision:

- **The site is static.** No backend, no database, no server. Just HTML files on Cloudflare Pages.
- **The data pipeline already exists.** `etoro_master.json` and the `generate_dashboard.py` script already produce the right outputs. Stage 2 is the public re-render of that, not a new computation.

### Data flow

```
Mon 5pm: ftse-tracker-weekly scheduled task runs
  -> regenerates C:\...\eToro\data\etoro_master.json with fresh signals
  -> existing valuation.py refreshes all 114 stocks

Mon ~5:15pm: NEW build script (build_site.py) runs
  -> reads etoro_master.json
  -> renders index.html (tracker), 114 ticker pages, methodology.html
  -> commits the rendered HTML to dalkent/daleyvaluations-site repo
  -> git push

Mon ~5:16pm: Cloudflare Pages auto-detects the push
  -> rebuilds and deploys in seconds
  -> daleyvaluations.com now serves the latest valuations
```

The build script is the only new piece. Everything else uses what's already there.

### What does NOT live in the public repo

- `etoro_master.json` itself stays private. Only the rendered HTML pages go public. This is important: the JSON contains every model output for every stock. Publishing the raw data exposes the methodology more granularly than necessary and removes any future option for an Excel-download paid tier.
- `combined_portfolio.json` similarly stays private. The portfolio page (Stage 4) shows curated holdings, not the full position log with entry prices and units.

The `.gitignore` already blocks `*.json` files, so this is enforced by construction.

## The design

### Information architecture

```
daleyvaluations.com/
  /                          - Homepage: live FTSE Valuation Tracker
  /methodology               - The methodology page (currently at /)
  /:ticker                   - Per-ticker page (114 of these)
  /portfolio                 - Read-only portfolio snapshot (Stage 4)
  /articles                  - Index of Substack articles by ticker (Stage 4)
```

Five routes total at the end of Stage 4. Modest and disciplined.

### Visual language

The methodology page already establishes the language:
- Ivory paper (`#f4f0e6`)
- Deep forest accent (`#0f2a1d`)
- Source Serif 4 for prose, Inter Tight for UI/data
- Warm grey (`#d8d2c2`) rules
- The five signal colours (Strong Buy forest, Buy mid-forest, Fair Value gold, Sell terracotta, Strong Sell brick)

Stage 2 extends this without changing it. New components inherit from the existing CSS variables.

### The tracker page (homepage)

Layout from top to bottom:

1. **Header strip** - same logo + brand row as the methodology page. A second row beneath it is a slim navigation: `Tracker · Methodology · Articles · Portfolio · About`. Always visible.

2. **Hero card** - one prominent card with three things:
   - The stamp "Last refreshed: 28 April 2026" (always honest about age of data)
   - A single-line summary: "114 stocks · 22 Strong Buy · 41 Fair Value · 18 Sell · 8 Strong Sell ·25 Buy" (computed at build time)
   - One "What changed this week" line: "5 signal upgrades, 3 downgrades. Biggest mover: $LLOY.L Sell -> Strong Sell."

3. **The table** - 114 rows. Columns:
   - Ticker (cashtag, links to per-ticker page)
   - Company (truncated to fit)
   - Sector
   - Current price
   - Blended target
   - Value ratio (number, 2 decimals)
   - Signal (coloured badge)
   - 1w change (signal moves shown as e.g. "Buy ↗" or "no change")

   Sortable by clicking column headers. Filterable by sector and signal via two dropdowns above the table. Defaults to sorted by Value Ratio descending (most undervalued first - the most useful default for a value-investor audience).

4. **Footer** - same as methodology page.

The table is the meat of the page. It must work on mobile (stack columns or horizontal scroll), must be accessible (keyboard nav, screen reader friendly), must load instantly (no server round-trip; sort/filter happens client-side on data already in the page).

### The per-ticker page

Layout from top to bottom:

1. **Header strip** - same nav.

2. **Ticker masthead** - prominent: ticker code, company name, sector, current price, signal badge.

3. **The blended target card** - large display: blended target price, value ratio, signal in coloured pill. The single most-useful number on the page.

4. **The three models** - small cards in a row:
   - DCF: value, weight in blend
   - DDM: value, weight in blend (or "Not used (sector)" if excluded)
   - EPV: value, weight in blend
   - For banks/insurers, the sector-specific models are named correctly (P/B Excess Returns, etc).

5. **The assumptions** - a small table:
   - Beta (clamped value)
   - WACC / Ke
   - Five-year growth (g1)
   - Terminal growth (g2)
   - Last updated

6. **Signal history** - a slim band showing the last 12 weeks of signal. If the data isn't there yet, this section is hidden until it is. Build this in once the JSON archive is long enough (3+ months).

7. **Articles on this stock** - bullet list of every Substack article that mentions this ticker. Links go to Substack. If none yet, the section is hidden.

8. **Disclaimer** - the standard "not advice, do your own research" block.

The page has no prose written by hand. Everything comes from the JSON. This is by design - the per-ticker pages are reference, not narrative. Substack is where the narrative lives.

### The /methodology page

Move the existing index.html to /methodology with no other changes. Add navigation header. Done.

## What we are NOT doing in Stage 2

Important to be explicit about this so scope doesn't creep:

- No charts. The tracker page is a table, not a dashboard. Adding interactive charts is Stage 3 territory at the earliest, and probably never (Substack articles are where charts go).
- No search. Sorting and filtering covers 90% of "find the stock I want" needs. Building search is high effort, low reward at 114 records.
- No login. No subscriber-gated content. The whole site is public.
- No comments. Substack has comments. The site does not.
- No notifications, RSS feed for the site, or email signup form on the site itself. Substack's email signup is the canonical way to get email; the site links to it. Don't build a parallel system.

## The build, in concrete steps

Each step is independently shippable. You can stop after any of them and the site still works.

### Step 1: Set up the build pipeline (one weekend)

Create `build_site.py` in the GitHub repo. The script:

- Reads `etoro_master.json` from the local `eToro/data` folder (path configured at top of script)
- Renders the tracker as `index.html` using a Jinja2 template
- Renders 114 ticker pages from a single Jinja2 template
- Renders the methodology page as `methodology.html` (preserves the current page's content, just at a new URL)
- Writes a `sitemap.xml` listing all pages for SEO
- Pushes everything to the repo via subprocess git commands

Wire it into the existing `ftse-tracker-weekly` scheduled task (Mon 5pm). The task currently regenerates the JSON; one extra step regenerates the site.

Key technical decisions:

- **Template engine: Jinja2.** Mature, light, exactly the right tool for this.
- **Data refresh frequency: weekly.** The site clearly states "Last refreshed: [date]" so the reader knows.
- **Stale data fallback: if JSON is older than 14 days, the site shows a banner saying "Data is being refreshed - some signals may be outdated."** Better to be honest than to show stale numbers as if they were fresh.

### Step 2: Build the tracker page (one weekend)

The 114-row table. Sort/filter via vanilla JavaScript (no frameworks). 50 lines of JS or so. The table itself is plain HTML rendered at build time.

The hero card stats ("22 Strong Buy, 41 Fair Value...") are computed at build time and baked into the HTML. No JavaScript needed for the static content.

### Step 3: Build the per-ticker pages (one weekend)

114 pages from one Jinja2 template. Each page is roughly 2-3kb of HTML. The whole site stays under 1MB total weight.

Each ticker page links back to `/` and to `/methodology` so readers can dig deeper or come back to the overview.

### Step 4: Add /methodology and navigation (half a day)

Move the existing index.html to /methodology.html. Add a slim nav header to all pages. Update internal links.

### Step 5: Submit sitemap to Google Search Console (10 minutes)

Verify the domain in Google Search Console. Submit `sitemap.xml`. Google starts indexing the per-ticker pages within a week. SEO compound begins.

### Stop here for two to four weeks

Sit with the live site. Watch traffic in Cloudflare Analytics (free, built into Pages). Watch which ticker pages get the most visits. Watch what searches bring people in. Do not build Stage 3 (portfolio page, articles index) until you have data on what readers actually want.

## Time and effort

| Step | Realistic time | Cumulative |
|---|---|---|
| 1. Build pipeline | 6-10 hours | 6-10 hours |
| 2. Tracker page | 6-10 hours | 12-20 hours |
| 3. Per-ticker pages | 4-6 hours | 16-26 hours |
| 4. Methodology + nav | 2-4 hours | 18-30 hours |
| 5. Sitemap submit | 0.5 hours | 18.5-30.5 hours |

Three to five weekends if you do it yourself. Two to three days if you outsource the front-end work to a freelancer (probably £400-700 at the rates a junior web dev would charge for this scope - it is a well-defined, low-risk brief).

## The honest pushback

Two real concerns worth thinking about before you commit:

**One: data quality goes from internal to public.** Right now if `etoro_master.json` has a wrong number, only you see it. Once the site is live, every wrong number is a public credibility hit. Before Stage 2 launches, the valuation script needs a sanity-check layer - flag stocks where the value ratio looks wildly off (e.g., < 0.2 or > 5.0), so you can review before the build runs. This is half a day of work and saves an embarrassing public mistake.

**Two: maintenance load.** A static site with weekly auto-refresh is genuinely low-maintenance, but it is not zero. Every quarter you should expect to touch the site (sector classifications change, Yahoo Finance breaks for a ticker, something in the build script needs adjusting). Budget a half-day per quarter for site keep-up. If that feels like too much on top of writing two articles a week, the site is overcommitting.

If both concerns clear, build the site. The case for it is stronger than the case against.

## What to do now (concrete next step)

Three options, in order of how much commitment they require:

1. **Approve this plan, set a build target date, schedule the work.** Say "we start Step 1 on Saturday 9 May, finish by Sunday 17 May." Concrete, time-boxed.

2. **Do a build spike first.** Spend two hours playing with `generate_dashboard.py` and reading the existing dashboard output before committing to the full plan. Validates the data pipeline assumption before writing any new code.

3. **Hold for now, revisit at 100 Substack subscribers.** Defer the build. The methodology page is enough for the moment. Build the tracker once the audience has grown enough that the SEO compound and credibility uplift justify the work.

I would push for option 1. The data pipeline is mature, the design is clear, the methodology page is already deployed, and the brand kit is locked. Doing this now while everything is fresh and the rebrand momentum is real costs less than coming back in three months and rebuilding context.

## Questions for the build session itself

These don't need answering today, but flag for when we start Step 1:

- Do you want the table to default-sort by Value Ratio descending (most undervalued first) or by signal (Strong Buy first)?
- Should US tickers in your portfolio (BMNR, NVO, etc.) appear on the site or only the FTSE 114?
- For the per-ticker pages, do you want the URL to be `/lloy-l` (matches the eToro ticker), `/lloy` (cleaner), or `/lloyds-banking-group` (most SEO-friendly)?
- Do you want to include an RSS feed for the per-ticker pages so subscribers can follow signal changes on a specific stock?

---

*Plan owner: Neil Daley*
*Last updated: 2026-04-29*
