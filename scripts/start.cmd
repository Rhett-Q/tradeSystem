@echo off
setlocal
cd /d "%~dp0.."

call "%~dp0setup_env.cmd"
if errorlevel 1 exit /b 1

call "%~dp0env.bat"
echo.
echo Testing MiniQMT connection ...
echo.

"%MINQMT_PYTHON_EXE%" -c "from minqmt.sync import MarketDataSync; s=MarketDataSync(); s.ensure_ready(); print('[OK] MiniQMT connected, universe size:', len(s.get_universe()))"
if errorlevel 1 (
    echo [WARN] Start MiniQMT client and login, then retry.
    exit /b 1
)

echo.
echo Ready. Start web dashboard:
echo   scripts\run_web.cmd
echo   http://127.0.0.1:8765
exit /b 0
