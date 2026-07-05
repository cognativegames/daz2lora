<#
.SYNOPSIS
    Nightly update: git pull + rebuild from source.
    Called by the app when update channel is "nightly".
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenPath  = Join-Path $RepoRoot ".venv"
$PipExe   = Join-Path $VenPath "Scripts\pip.exe"
$PyExe    = Join-Path $VenPath "Scripts\python.exe"

# Wait for the running app to exit
Start-Sleep -Seconds 3

# Pull latest
git -C $RepoRoot pull --rebase

# Install any dep changes
& $PipExe install -e "$RepoRoot" --quiet

# Rebuild
& $PipExe install pyinstaller --quiet
& $PyExe -m PyInstaller --noconfirm `
    --name "daz2lora" `
    --windowed `
    --add-data "src/daz2lora/daz_scripts;daz2lora/daz_scripts" `
    --paths "src" `
    --distpath "dist" `
    --workpath "build" `
    (Join-Path $RepoRoot "src/daz2lora/main.py")

$ExePath = Join-Path $RepoRoot "dist\daz2lora\daz2lora.exe"
if (Test-Path $ExePath) {
    Start-Process $ExePath
}
