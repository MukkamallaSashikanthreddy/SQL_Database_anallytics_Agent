@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    echo Python launcher was not found. Install Python 3.11 or newer and retry.
    pause
    exit /b 1
)
py -3.11 -m venv .venv
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :error
if not exist ".env" copy .env.example .env >nul
if not exist "database\analytics.db" .venv\Scripts\python.exe -m database.seed
if errorlevel 1 goto :error
echo.
echo Setup complete. Run run_windows.bat to launch the Streamlit application.
pause
goto :eof
:error
echo Setup failed. Review the error above.
pause
exit /b 1
