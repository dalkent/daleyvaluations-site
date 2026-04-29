# How to refresh the live site

Two batch files at the repo root, each does a complete pipeline. Double-click one and walk away.

## refresh-site.bat (lighter, ~30 seconds)

Use this when the underlying valuations have not changed but you want to:
- Refresh live prices on the site (fetches from Yahoo Finance)
- Pick up any HTML/CSS/template tweaks you've made
- Force a redeploy after a fix

What it runs:
1. `python scripts\build_site.py --refresh-prices`
2. `git add . && git commit && git push`

## full-refresh.bat (full pipeline, ~1-2 minutes)

Use this when you want the absolute latest valuations on the site:
- Start-of-week deploys (Monday after the markets open)
- After updating any model assumptions in valuation.py
- After material changes to eToro_Master.xlsx

What it runs:
1. `python C:\Users\Neil\ClaudeCode\eToro\scripts\valuation.py` (regenerates etoro_master.json with fresh yfinance data and three-model blend)
2. `python scripts\build_site.py --refresh-prices`
3. `git add . && git commit && git push`

## What happens after the push

Cloudflare Pages detects the push within seconds, builds (no build step needed for static HTML so this is near-instant), and propagates to its global CDN. From `git push` to "live for new visitors": about 60 seconds.

Existing visitors with the page cached in their browser may need a hard refresh (Ctrl+Shift+R) to see the new version.

## If something fails

Each step prints a clear ERROR and pauses the window so you can read it. Common issues:

- **valuation.py errors** — the eToro project might have a missing dependency or a Yahoo Finance hiccup. Re-run, or check the eToro project directly.
- **build_site.py errors** — the etoro_master.json might be malformed. The script auto-recovers from truncated JSON, so this is rare. If it does fail, look at the WARNINGS.
- **git push fails with auth error** — your GitHub Personal Access Token may have expired. Regenerate at github.com → Settings → Developer settings → Personal access tokens. Username is `dalkent`, paste the token as the password.
- **Cloudflare deploy fails** — visit dash.cloudflare.com → Workers & Pages → daleyvaluations → Deployments tab. The build log shows the error. Often a transient platform issue; click "Retry deployment".

## To make this fully automatic

Right now you double-click the batch file when you want to refresh. To make it run on a schedule:

1. Open Windows Task Scheduler
2. Create a new basic task: "Daley Valuations Weekly Refresh"
3. Trigger: Weekly, Monday, 5:30pm
4. Action: Start a program
5. Program: `C:\Users\Neil\My Drive\Daley's Brain\Projects\eToro & Investing\Drafts\daleyvaluations-site\full-refresh.bat`
6. Save

That makes the site auto-refresh every Monday afternoon. Recommended once you've done 2-3 manual cycles and confirmed the pipeline is reliable on your machine.
