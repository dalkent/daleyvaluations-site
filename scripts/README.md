# Scripts

Build automation for daleyvaluations.com.

## build_site.py

The main build script. Reads `etoro_master.json` from the local eToro data folder, renders all public pages as static HTML, writes them to the repo root.

Run manually:
```
python scripts/build_site.py
```

Run from the `ftse-tracker-weekly` scheduled task: invoked after the tracker JSON regenerates, so the public site reflects the latest signals every Monday by ~5:30pm.

## Status

Currently a stub. The data pipeline is wired (loads JSON, joins valuations + watchlist into one record per ticker, runs sanity checks). The renderers are stubs that raise `NotImplementedError`.

Build steps to complete, in order:

1. Sanity-check layer (DONE - in stub)
2. Tracker page template + renderer
3. Per-ticker page template + renderer
4. Methodology page move (currently at `/`, becomes `/methodology`)
5. Sitemap generation (DONE - in stub)
6. Wire into the scheduled task

See `PLAN-STAGE-2.md` at the repo root for the full plan.

## Why this script lives in the site repo, not the eToro data repo

The eToro repo (`C:\Users\Neil\ClaudeCode\eToro`) is private and contains the live valuation script, portfolio data, and the spreadsheet. It is not in version control on GitHub.

This site repo (`dalkent/daleyvaluations-site`) is public and version-controlled. The build script that consumes the private data and produces public HTML lives here so that:

- The site repo's git history shows every site change
- The build is reproducible (clone the repo, run the script, get the same HTML)
- The boundary between private data and public output is enforced by which folder a file lives in
