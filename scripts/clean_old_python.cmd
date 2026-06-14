@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo  Remove old Python versions (keep 3.9 / 3.10 / 3.11)
echo ============================================================
echo.

REM Prefer a real Python to run the cleaner (not WindowsApps stub)
set "RUNNER="

if exist "D:\Python\Python39\python.exe" set "RUNNER=D:\Python\Python39\python.exe"
if exist "D:\Python\Python38\python.exe" if not defined RUNNER set "RUNNER=D:\Python\Python38\python.exe"
if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" if not defined RUNNER set "RUNNER=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
if not defined RUNNER where py >nul 2>&1 && (
    for /f "delims=" %%P in ('py -3.8 -c "import sys; print(sys.executable)" 2^>nul') do set "RUNNER=%%P"
)
if not defined RUNNER where py >nul 2>&1 && (
    for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "RUNNER=%%P"
)

if not defined RUNNER (
    echo [ERROR] Need any working Python to run the cleaner.
    echo Install Python 3.9 first, or run from an existing install:
    echo   D:\Python\Python38\python.exe scripts\clean_old_python.py --list
    exit /b 1
)

echo Using: %RUNNER%
echo.

if "%~1"=="--list" (
    "%RUNNER%" "%~dp0clean_old_python.py" --list
    exit /b %errorlevel%
)

if "%~1"=="--dry-run" (
    "%RUNNER%" "%~dp0clean_old_python.py" --dry-run
    exit /b %errorlevel%
)

if "%~1"=="--yes" (
    "%RUNNER%" "%~dp0clean_old_python.py" --yes
    exit /b %errorlevel%
)

echo Preview (dry-run):
"%RUNNER%" "%~dp0clean_old_python.py" --dry-run
echo.
echo To uninstall old versions, run:
echo   scripts\clean_old_python.cmd --yes
echo.
exit /b 0
