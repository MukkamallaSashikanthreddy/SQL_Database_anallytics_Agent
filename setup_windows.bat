@echo off
setlocal
cd /d "%~dp0"
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
echo Setup completed. Edit .env and set GOOGLE_API_KEY before running Gemini mode.
echo Run: .venv\Scripts\streamlit.exe run app.py
pause
exit /b 0
:error
echo Setup failed. Review the error above.
pause
exit /b 1
