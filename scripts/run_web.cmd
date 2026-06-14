@echo off
setlocal
cd /d "%~dp0.."

call "%~dp0setup_env.cmd"
if errorlevel 1 exit /b 1

call "%~dp0env.bat"

"%MINQMT_PYTHON_EXE%" -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo Installing web dependencies ...
    "%MINQMT_PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
)

echo.
echo Starting web server at http://127.0.0.1:8765
echo.

"%MINQMT_PYTHON_EXE%" "%~dp0run_web.py"
exit /b %errorlevel%
