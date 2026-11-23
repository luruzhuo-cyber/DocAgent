@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Missing .venv. See README.md for setup.
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn docagent.api:app --host 127.0.0.1 --port 8011
