@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setting up PanelForge for the first time...
  py -3 -m venv .venv 2>nul || python -m venv .venv
  if errorlevel 1 goto :error
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
start "" "http://127.0.0.1:5000"
echo PanelForge is running. Keep this window open.
echo Open http://127.0.0.1:5000 if your browser does not open.
".venv\Scripts\python.exe" app.py
exit /b
:error
echo.
echo Setup failed. Make sure Python 3.10 or newer is installed.
pause
exit /b 1
