# Start MiniQMT web dashboard
# Usage: .\scripts\run_web.ps1

$ErrorActionPreference = "Stop"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "setup_env.ps1")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$py = $env:MINQMT_PYTHON
if (-not $py) { $py = "python" }

Write-Host ""
Write-Host "Starting web server at http://127.0.0.1:8765"
Write-Host ""

if ($py -match "^py -") {
    $ver = ($py -split " ", 2)[1]
    & py $ver (Join-Path $PSScriptRoot "run_web.py")
} else {
    & python (Join-Path $PSScriptRoot "run_web.py")
}
