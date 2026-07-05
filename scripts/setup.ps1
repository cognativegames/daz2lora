<#
.SYNOPSIS
    Bootstrap daz2lora on a fresh Windows PC — checks Python, creates venv,
    installs deps, builds the .exe, and optionally creates a desktop shortcut.

.DESCRIPTION
    Run this on a fresh Windows 10/11 machine. It will:
    1. Check for Python 3.11+. Offer to install it if missing.
    2. Create a virtual environment.
    3. Install the app and PyInstaller.
    4. Build daz2lora.exe via PyInstaller.
    5. (Optional) Create a Start Menu shortcut.

    Usage:
        powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#>

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenPath  = Join-Path $RepoRoot ".venv"
$DistPath = Join-Path $RepoRoot "dist"

Write-Host "=== daz2lora Windows Setup ===" -ForegroundColor Cyan

# ─── 1. Check Python ──────────────────────────────────────────────────────────

$PythonExe = $null
$MinVersion = [Version]"3.11.0"

# Try python and python3
foreach ($cmd in @("python", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "(\d+\.\d+\.\d+)") {
            $v = [Version]$matches[1]
            if ($v -ge $MinVersion) {
                $PythonExe = (Get-Command $cmd).Source
                Write-Host "Found Python $v at $PythonExe" -ForegroundColor Green
                break
            }
        }
    } catch {}
}

if (-not $PythonExe) {
    Write-Host "Python 3.11+ not found." -ForegroundColor Yellow
    $choice = Read-Host "Download and install Python 3.13? (y/n)"
    if ($choice -eq "y") {
        $url = "https://www.python.org/ftp/python/3.13.2/python-3.13.2-amd64.exe"
        $installer = "$env:TEMP\python-3.13.2-amd64.exe"
        Write-Host "Downloading Python 3.13..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $url -OutFile $installer
        Write-Host "Running installer (check 'Add to PATH')..." -ForegroundColor Cyan
        Start-Process -Wait -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1"
        $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
        $PythonExe = (Get-Command python).Source
        Write-Host "Python installed at $PythonExe" -ForegroundColor Green
    } else {
        Write-Host "Install Python manually from https://python.org, then re-run this script." -ForegroundColor Red
        exit 1
    }
}

# ─── 2. Create venv ───────────────────────────────────────────────────────────

if (Test-Path $VenPath) {
    Write-Host "Removing old .venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VenPath
}

Write-Host "Creating virtual environment..." -ForegroundColor Cyan
& $PythonExe -m venv $VenPath
if (-not $?) { throw "Failed to create venv" }

$PipExe = Join-Path $VenPath "Scripts\pip.exe"

# ─── 3. Install deps ──────────────────────────────────────────────────────────

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $PipExe install -e "$RepoRoot" --quiet
if (-not $?) { throw "pip install failed" }

Write-Host "Installing PyInstaller..." -ForegroundColor Cyan
& $PipExe install pyinstaller --quiet
if (-not $?) { throw "PyInstaller install failed" }

# ─── 4. Build .exe ────────────────────────────────────────────────────────────

Write-Host "Building daz2lora.exe..." -ForegroundColor Cyan
$PyExe = Join-Path $VenPath "Scripts\python.exe"
& $PyExe -m PyInstaller --noconfirm `
    --name "daz2lora" `
    --windowed `
    --add-data "src/daz2lora/daz_scripts;daz2lora/daz_scripts" `
    --paths "src" `
    --distpath "dist" `
    --workpath "build" `
    (Join-Path $RepoRoot "src/daz2lora/main.py")

if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$ExePath = Join-Path $DistPath "daz2lora\daz2lora.exe"
Write-Host "✓ Built: $ExePath" -ForegroundColor Green

# ─── 5. Desktop shortcut (optional) ──────────────────────────────────────────

$choice = Read-Host "Create Start Menu shortcut? (y/n)"
if ($choice -eq "y") {
    $WScriptShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WScriptShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\daz2lora.lnk")
    $Shortcut.TargetPath = $ExePath
    $Shortcut.WorkingDirectory = $RepoRoot
    $Shortcut.Save()
    Write-Host "✓ Shortcut created in Start Menu" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Setup complete ===" -ForegroundColor Cyan
Write-Host "Run: $ExePath" -ForegroundColor Green
Write-Host "Or:  .venv\Scripts\python -m daz2lora.main"
