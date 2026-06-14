# MiniQMT env setup for Windows PowerShell
# Usage: .\scripts\setup_env.ps1
# Optional: $env:QMT_ROOT = "D:\your\qmt\path" before running

param(
    [string]$QmtRootOverride = $env:QMT_ROOT
)

$QmtRoots = @()
if ($QmtRootOverride) {
    $QmtRoots += $QmtRootOverride
}
$QmtRoots += "D:\gjqmt"

$SubPaths = @(
    "bin.x64\Lib\site-packages",
    "bin\Lib\site-packages",
    "Lib\site-packages"
)

$xtPath = $null
$qmtRoot = $null

foreach ($root in $QmtRoots) {
    if (-not $root -or -not (Test-Path -LiteralPath $root)) { continue }
    foreach ($sub in $SubPaths) {
        $candidate = Join-Path $root $sub
        $xtDir = Join-Path $candidate "xtquant"
        if (Test-Path -LiteralPath $xtDir) {
            $xtPath = $candidate
            $qmtRoot = $root
            break
        }
    }
    if ($xtPath) { break }
}

if (-not $xtPath) {
    Write-Host "[ERROR] xtquant not found." -ForegroundColor Red
    Write-Host "Set QMT_ROOT to your MiniQMT install folder, e.g.:"
    Write-Host '  $env:QMT_ROOT = "D:\gjqmt"'
    Write-Host "  .\scripts\setup_env.ps1"
    exit 1
}

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))
$workDir = Get-Location

$binX64 = Join-Path $qmtRoot "bin.x64"
$xtquantDir = Join-Path $xtPath "xtquant"

$env:QMT_ROOT = $qmtRoot
$env:MINQMT_WORKSPACE = $workDir.Path
$env:PYTHONPATH = $workDir.Path

# Native DLLs (log4cxx, openssl, etc.) live under bin.x64 and xtquant/
$env:PATH = $binX64 + ";" + $xtquantDir + ";" + $env:PATH

function Test-XtquantImport {
    param([string]$PyLauncher)
    $code = @'
import os, sys
from pathlib import Path
qmt = Path(os.environ['QMT_ROOT'])
bin_x64 = qmt / 'bin.x64'
xt_site = bin_x64 / 'Lib' / 'site-packages'
if str(xt_site) not in sys.path:
    sys.path.append(str(xt_site))
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(str(bin_x64))
    os.add_dll_directory(str(xt_site / 'xtquant'))
from xtquant import xtdata
print("[OK] xtquant import success")
'@
    if ($PyLauncher -match "^py -") {
        $ver = ($PyLauncher -split " ", 2)[1]
        & py $ver -c $code 2>$null
    } else {
        & $PyLauncher -c $code 2>$null
    }
    return ($LASTEXITCODE -eq 0)
}

# Prefer newer Python; skip 3.8 if cp38 pyd is broken (imports python27.dll)
$pyCandidates = @("3.11", "3.10", "3.9", "3.8", "3.7", "3.6")
$py = $null

if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($ver in $pyCandidates) {
        & py "-$ver" -c "import sys" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { continue }
        if (Test-XtquantImport "py -$ver") {
            $py = "py -$ver"
            break
        }
    }
}

if (-not $py) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        if (Test-XtquantImport "python") { $py = "python" }
    }
}

if (-not $py) {
    Write-Host "[ERROR] xtquant import failed for all installed Python versions." -ForegroundColor Red
    Write-Host ""
    Write-Host "Your QMT cp38 extension may be broken (needs python27.dll instead of python38.dll)."
    Write-Host "Recommended fix:"
    Write-Host "  1. Install Python 3.9 or 3.10 (64-bit) from python.org"
    Write-Host "  2. Re-run: .\scripts\setup_env.ps1"
    Write-Host ""
    Write-Host "Or re-download xtquant in QMT: Settings > Model settings > Python library download"
    Write-Host ""
    Write-Host "Run diagnostics:"
    Write-Host "  py -3.8 scripts\diagnose_xtquant.py"
    exit 1
}

$env:MINQMT_PYTHON = $py

Write-Host "[OK] QMT_ROOT      = $qmtRoot"
Write-Host "[OK] PYTHONPATH    = $xtPath"
Write-Host "[OK] PATH          += $binX64; $xtquantDir"
Write-Host "[OK] MINQMT_PYTHON = $py"
Write-Host "[OK] WORKDIR       = $workDir"
Write-Host ""
Write-Host "Testing xtquant import ..."

if ($py -match "^py -") {
    $ver = ($py -split " ", 2)[1]
    & py $ver -c "from minqmt.qmt_bootstrap import configure_qmt; configure_qmt(); from xtquant import xtdata; print('[OK] xtquant import success')"
} else {
    & python -c "from minqmt.qmt_bootstrap import configure_qmt; configure_qmt(); from xtquant import xtdata; print('[OK] xtquant import success')"
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] xtquant import failed. Start and login MiniQMT first." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  $py scripts\sync_market.py universe"
Write-Host "  $py scripts\sync_market.py full --start 20200101"
Write-Host "  $py scripts\sync_market.py incremental"
