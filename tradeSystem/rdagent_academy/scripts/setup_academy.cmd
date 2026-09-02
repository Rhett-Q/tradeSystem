@echo off
setlocal
cd /d "%~dp0.."

echo === RD-Agent Academy setup ===

rem Prefer 3.11+; fall back to py -3
set "PY=py -3.11"
%PY% -V >nul 2>&1
if errorlevel 1 set "PY=py -3"

%PY% -V
if errorlevel 1 (
  echo [ERROR] 需要 Python Launcher: py
  exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
  echo 创建 backend venv ...
  %PY% -m venv backend\.venv
  if errorlevel 1 exit /b 1
)

echo 安装 backend 依赖 ...
backend\.venv\Scripts\python.exe -m pip install -U pip
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 exit /b 1

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] 需要 Node.js / npm
  exit /b 1
)

echo 安装 frontend 依赖 ...
pushd frontend
call npm install
if errorlevel 1 (
  popd
  exit /b 1
)
popd

echo.
echo Setup 完成。运行: rdagent_academy\scripts\run_academy.cmd
endlocal
