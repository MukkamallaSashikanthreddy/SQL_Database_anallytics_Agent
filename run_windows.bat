@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment not found. Run setup_windows.bat first.
    pause
    exit /b 1
)
if not exist "database\analytics.db" (
    .venv\Scripts\python.exe -m database.seed
    if errorlevel 1 goto :error
)
.venv\Scripts\python.exe -m streamlit run app.py
if errorlevel 1 goto :error
goto :eof
:error
echo Application did not start. Review the error above.
pause
