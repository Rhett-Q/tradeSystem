@echo off
setlocal
cd /d "%~dp0.."

echo Installing Python 3.9 via winget (requires admin may prompt)...
echo.

where winget >nul 2>&1
if errorlevel 1 (
    echo [ERROR] winget not found. Download Python 3.9 manually:
    echo   https://www.python.org/downloads/release/python-3913/
    exit /b 1
)

winget install -e --id Python.Python.3.9 --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo.
    echo If winget failed, download and install manually:
    echo   https://www.python.org/downloads/release/python-3913/
    exit /b 1
)

echo.
echo Python 3.9 installed. Recommended next steps:
echo   scripts\clean_old_python.cmd --yes
echo   scripts\setup_env.cmd
exit /b 0
