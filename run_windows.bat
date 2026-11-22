@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\streamlit.exe" (
  echo Virtual environment missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\streamlit.exe run app.py
