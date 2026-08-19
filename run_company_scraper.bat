@echo off
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Error: .venv Python executable not found.
    pause
    popd
    exit /b 1
)

.venv\Scripts\python.exe company_scraper.py
set "exit_code=%errorlevel%"

popd
pause
exit /b %exit_code%
