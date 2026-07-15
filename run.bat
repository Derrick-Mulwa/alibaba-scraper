@echo off
REM 1. Activate the virtual environment
call .venv\Scripts\activate

REM 2. Run your script using cmd /k
cmd /k .venv\Scripts\python.exe main.py

REM The pause below will only execute if you manually exit the cmd /k session
pause
