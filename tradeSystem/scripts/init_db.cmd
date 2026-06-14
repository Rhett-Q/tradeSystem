@echo off
cd /d "%~dp0..\backend"
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
python scripts\init_db.py
pause
