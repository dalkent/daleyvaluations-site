@echo off
REM ============================================================================
REM full-refresh.bat
REM
REM Full pipeline: regenerate the valuations JSON, rebuild the site, deploy.
REM
REM This runs every step end-to-end:
REM   1. Run valuation.py to recompute all 127 stock valuations from Yahoo
REM   2. Rebuild the Daley Valuations site HTML
REM   3. Commit and push to GitHub (Cloudflare auto-deploys)
REM
REM Use this when:
REM   - You want the very latest valuations on the live site
REM   - It's the start of the trading week and you want fresh signals
REM   - You haven't run valuation.py separately and want one-click everything
REM
REM Total time: roughly 1-2 minutes
REM ============================================================================

setlocal

REM Path to the eToro project (where valuation.py lives)
set "ETORO_DIR=C:\Users\Neil\ClaudeCode\eToro"

REM This script's own directory (the site repo)
set "SITE_DIR=%~dp0"
REM Strip trailing backslash for cleaner messages
if "%SITE_DIR:~-1%"=="\" set "SITE_DIR=%SITE_DIR:~0,-1%"

echo.
echo ====================================================
echo Daley Valuations - Full Refresh Pipeline
echo ====================================================
echo.

REM ---- Step 1: regenerate valuations ----
echo [1/4] Regenerating etoro_master.json from valuation.py...
echo       (Fetches live yfinance data and runs DCF/DDM/EPV on all 127 stocks)
echo.

if not exist "%ETORO_DIR%" (
    echo ERROR: eToro directory not found at %ETORO_DIR%
    echo Update ETORO_DIR at the top of this script if your path differs.
    pause
    exit /b 1
)

cd /d "%ETORO_DIR%"

REM Run the valuation script. Adjust the path/filename if it lives elsewhere.
if exist "scripts\valuation.py" (
    python scripts\valuation.py
) else if exist "valuation.py" (
    python valuation.py
) else (
    echo ERROR: Could not find valuation.py in %ETORO_DIR% or %ETORO_DIR%\scripts
    pause
    exit /b 1
)

if errorlevel 1 (
    echo.
    echo ERROR: valuation.py failed. Check the output above.
    pause
    exit /b 1
)

REM ---- Step 2: rebuild the site ----
echo.
echo [2/4] Rebuilding site with fresh Yahoo Finance prices...
cd /d "%SITE_DIR%"
python scripts\build_site.py --refresh-prices
if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above.
    pause
    exit /b 1
)

REM ---- Step 3: stage and commit ----
echo.
echo [3/4] Committing changes to Git...

git add .
git diff --cached --quiet
if %errorlevel% equ 0 (
    echo No changes to commit. Site already up to date with current data.
    pause
    exit /b 0
)

for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set DATESTAMP=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ("%time%") do set TIMESTAMP=%%a:%%b
git commit -m "Full refresh: %DATESTAMP% %TIMESTAMP%"
if errorlevel 1 (
    echo.
    echo ERROR: Commit failed. Check the output above.
    pause
    exit /b 1
)

REM ---- Step 4: push to GitHub ----
echo.
echo [4/4] Pushing to GitHub (Cloudflare will auto-deploy)...
git push
if errorlevel 1 (
    echo.
    echo ERROR: Push failed. Check the output above.
    echo If credentials prompt: username = dalkent, password = your GitHub token (ghp_...)
    pause
    exit /b 1
)

echo.
echo ====================================================
echo SUCCESS: Full pipeline complete.
echo Cloudflare deploy usually completes within 60 seconds.
echo Live at: https://daleyvaluations.com
echo ====================================================
echo.
pause
endlocal
