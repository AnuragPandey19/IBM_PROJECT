@echo off
setlocal EnableExtensions

REM ===========================================================
REM   git-push.bat
REM   Stages everything, commits with current date/time,
REM   and pushes to the configured remote.
REM   Drop this into any git repo and double-click to push.
REM ===========================================================

REM Always operate in the folder this script lives in
cd /d "%~dp0"

REM Build a clean timestamp via PowerShell (locale-safe format)
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm'"') do set "TIMESTAMP=%%i"

echo.
echo ============================================================
echo   Git auto-push
echo   Folder    : %CD%
echo   Message   : %TIMESTAMP%
echo ============================================================
echo.

REM Make sure we're in a git repo before touching anything
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This folder is not a git repository.
    echo         Run "git init" here first, or move this script
    echo         into a folder that already has git initialized.
    echo.
    pause
    exit /b 1
)

REM ---- Stage all changes ----
echo [1/3] Staging changes...
git add .
echo.

REM ---- Commit (will print "nothing to commit" if no changes - that's fine) ----
echo [2/3] Committing as "%TIMESTAMP%"...
git commit -m "%TIMESTAMP%"
echo.

REM ---- Push to Hugging Face (deployment) ----
echo [3/4] Pushing to Hugging Face (hf)...
git push hf main
if errorlevel 1 (
    echo.
    echo [WARNING] HF push failed. Continuing to GitHub anyway.
    echo   Common causes:
    echo   - Auth issue          -^> refresh HF token
    echo   - Large file blocked  -^> check Git LFS
    echo.
    set "HF_FAILED=1"
) else (
    echo [OK] HF push succeeded.
)

echo.

REM ---- Push to GitHub (team sharing) ----
echo [4/4] Pushing to GitHub (github)...
git push github main
if errorlevel 1 (
    echo.
    echo [WARNING] GitHub push failed. Common causes:
    echo   - Remote not added    -^> git remote add github ^<url^>
    echo   - No upstream branch  -^> git push -u github main (first time)
    echo   - Timeout on big push -^> git config --global http.postBuffer 524288000
    echo.
    pause
    exit /b 1
) else (
    echo [OK] GitHub push succeeded.
)

echo.
echo ============================================================
if defined HF_FAILED (
    echo   Done. GitHub OK but HF push had an issue - review above.
) else (
    echo   Done. All changes pushed to BOTH remotes.
)
echo ============================================================
echo.
pause
