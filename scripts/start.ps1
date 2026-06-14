# Configure env and test MiniQMT connection
# Usage: .\scripts\start.ps1

$ErrorActionPreference = "Stop"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "setup_env.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$py = $env:MINQMT_PYTHON
if (-not $py) { $py = "python" }

Write-Host ""
Write-Host "Testing MiniQMT connection ..."

$code = @'
from minqmt.sync import MarketDataSync
sync = MarketDataSync()
sync.ensure_ready()
n = len(sync.get_universe())
print("[OK] MiniQMT connected, universe size:", n)
'@

if ($py -eq "py -3.8") {
    & py -3.8 -c $code
} else {
    & python -c $code
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Start MiniQMT client and login, then retry." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Ready. Start web dashboard:"
Write-Host "  .\scripts\run_web.ps1"
Write-Host "  http://127.0.0.1:8765"
