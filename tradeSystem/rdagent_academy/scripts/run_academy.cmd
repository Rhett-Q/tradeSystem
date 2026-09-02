@echo off
setlocal
cd /d "%~dp0.."

if not exist "backend\.venv\Scripts\python.exe" (
  echo 请先运行 scripts\setup_academy.cmd
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo 请先运行 scripts\setup_academy.cmd
  exit /b 1
)

echo === RD-Agent Academy ===
echo API  http://127.0.0.1:19900
echo Web  http://127.0.0.1:19901
echo.

start "RD-Agent Academy API" /D "%~dp0..\backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 19900"
timeout /t 2 /nobreak >nul
start "RD-Agent Academy UI" /D "%~dp0..\frontend" cmd /k "npm run dev"

echo 已在新窗口启动 API 与前端。浏览器打开 http://127.0.0.1:19901
endlocal
