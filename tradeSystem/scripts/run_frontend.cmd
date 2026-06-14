@echo off
cd /d "%~dp0..\frontend"
if not exist node_modules (
  echo Installing frontend dependencies...
  call npm install
)
echo Starting Vite dev server on http://127.0.0.1:5173
call npm run dev
