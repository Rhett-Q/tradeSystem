@echo off
setlocal
cd /d "%~dp0.."

if exist "%~dp0env.bat" (
    call "%~dp0env.bat"
) else (
    call "%~dp0setup_env.cmd"
    if errorlevel 1 exit /b 1
    call "%~dp0env.bat"
)

echo Installing dependencies ...
"%MINQMT_PYTHON_EXE%" -m pip install -r requirements.txt
exit /b %errorlevel%
