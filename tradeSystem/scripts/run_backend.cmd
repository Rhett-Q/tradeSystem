@echo off
cd /d "%~dp0..\backend"
if not exist .venv (
  echo Creating Python venv...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q

for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8000.*LISTENING"') do (
  echo [WARN] Port 8000 is already in use by PID %%a
  echo        Stop the old backend first, or run: taskkill /PID %%a /F
  pause
  exit /b 1
)

echo Starting FastAPI on http://127.0.0.1:8000
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
