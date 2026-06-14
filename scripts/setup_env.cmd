@echo off
setlocal
cd /d "%~dp0.."

REM Prefer real installs — never rely on WindowsApps python stubs

if exist "D:\Python\Python39\python.exe" (
    "D:\Python\Python39\python.exe" "%~dp0setup_env.py"
    exit /b %errorlevel%
)

if exist "D:\Python\Python310\python.exe" (
    "D:\Python\Python310\python.exe" "%~dp0setup_env.py"
    exit /b %errorlevel%
)

if exist "D:\Python\Python311\python.exe" (
    "D:\Python\Python311\python.exe" "%~dp0setup_env.py"
    exit /b %errorlevel%
)

if exist "D:\Python\Python38\python.exe" (
    "D:\Python\Python38\python.exe" "%~dp0setup_env.py"
    exit /b %errorlevel%
)

if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" "%~dp0setup_env.py"
    exit /b %errorlevel%
)

if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" "%~dp0setup_env.py"
    exit /b %errorlevel%
)

where py >nul 2>&1 && (
    py -3.9 "%~dp0setup_env.py" 2>nul
    if not errorlevel 1 exit /b 0
    py -3.8 "%~dp0setup_env.py" 2>nul
    if not errorlevel 1 exit /b 0
    py -3 "%~dp0setup_env.py" 2>nul
    if not errorlevel 1 exit /b 0
)

echo [ERROR] No usable Python found.
echo.
echo Install 64-bit Python 3.9: scripts\install_python39.cmd
echo Or download: https://www.python.org/downloads/
echo.
echo Also disable Windows Store aliases:
echo   Settings ^> Apps ^> Advanced ^> App execution aliases
echo   Turn OFF python.exe and python3.exe
exit /b 1
