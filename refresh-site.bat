@echo off
REM ============================================================================
REM refresh-site.bat
REM
REM Rebuilds the Daley Valuations site from the latest etoro_master.json
REM and pushes to GitHub. Cloudflare Pages auto-deploys on push.
REM
REM Use this when:
REM   - You want to refresh the site with current Yahoo prices
REM   - The eToro_Master.xlsx valuations have not changed
REM   - You just want to redeploy the existing data with a new build
REM
REM For a full pipeline (regenerate JSON + rebuild + deploy), use:
REM   full-refresh.bat
REM ============================================================================

setlocal

REM Always run from this script's directory, regardless of where it's invoked from
cd /d "%~dp0"

echo.
echo ====================================================
echo Daley Valuations - Site Refresh
echo ====================================================
echo.

REM ---- Step 1: rebuild the site ----
echo [1/3] Rebuilding site with fresh Yahoo Finance prices...
python scripts\build_site.py --refresh-prices
if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above.
    pause
    exit /b 1
)

REM ---- Step 2: stage and commit ----
echo.
echo [2/3] Committing changes to Git...

REM Check if there's anything to commit
git diff --quiet
set "STAGED=%errorlevel%"
git diff --cached --quiet
set "CACHED=%errorlevel%"

git add .
git diff --cached --quiet
if %errorlevel% equ 0 (
    echo No changes to commit. Site already up to date.
    pause
    exit /b 0
)

REM Build a commit message with the current UK timestamp
for /f "tokens=1-3 delims=/ " %%a in ("%date%") do set DATESTAMP=%%c-%%b-%%a
for /f "tokens=1-2 delims=: " %%a in ("%time%") do set TIMESTAMP=%%a:%%b
git commit -m "Refresh tracker: %DATESTAMP% %TIMESTAMP%"
if errorlevel 1 (
    echo.
    echo ERROR: Commit failed. Check the output above.
    pause
    exit /b 1
)

REM ---- Step 3: push to GitHub ----
echo.
echo [3/3] Pushing to GitHub (Cloudflare will auto-deploy)...
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
echo SUCCESS: Site refresh pushed to GitHub.
echo Cloudflare deploy usually completes within 60 seconds.
echo Live at: https://daleyvaluations.com
echo ====================================================
echo.
pause
endlocal
