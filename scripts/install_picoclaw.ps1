# ============================================================================
# IRIS AI Office System - PicoClaw MCP Bridge Installer
# Sipeed PicoClaw: Go-based ultra-lightweight AI with native MCP protocol
# Memory footprint: <10MB RAM | Startup: <200ms | Port: 8765
#
# Usage:
#   .\scripts\install_picoclaw.ps1
#   .\scripts\install_picoclaw.ps1 -ConfigOnly    # Skip download, just write config
#
# PicoClaw acts as a unified HTTP gateway for all your MCP servers.
# Agents call POST http://localhost:8765/mcp/call with:
#   { "server": "brave-search", "tool": "search", "arguments": {...} }
# ============================================================================

param(
    [switch]$ConfigOnly = $false,
    [string]$InstallDir = "$env:LOCALAPPDATA\PicoClaw"
)

$ErrorActionPreference = "Stop"

$PICOCLAW_CONFIG  = "$PSScriptRoot\picoclaw_config.yaml"
$PICOCLAW_EXE     = "$InstallDir\picoclaw.exe"

Write-Host ""
Write-Host "=== IRIS PicoClaw MCP Bridge Installer ===" -ForegroundColor Cyan
Write-Host ""

# 1. Create install directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir | Out-Null
    Write-Host "[+] Created install directory: $InstallDir" -ForegroundColor Green
}

# 2. Download binary
if (-not $ConfigOnly) {
    Write-Host "[~] Discovering latest PicoClaw release..." -ForegroundColor Yellow

    try {
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/sipeed/picoclaw/releases/latest" `
            -Headers @{ "User-Agent" = "IRIS-AI-Office" }
        $asset = $release.assets | Where-Object { $_.name -eq "picoclaw_Windows_x86_64.zip" } | Select-Object -First 1
        if (-not $asset) {
            throw "Windows x86_64 asset not found in latest release $($release.tag_name)."
        }

        $tmpRoot = [System.IO.Path]::GetFullPath($env:TEMP)
        $tmpZip = Join-Path $tmpRoot "picoclaw_Windows_x86_64.zip"
        $tmpDir = Join-Path $tmpRoot "picoclaw_extract"
        $tmpDirFull = [System.IO.Path]::GetFullPath($tmpDir)
        if (-not $tmpDirFull.StartsWith($tmpRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Unsafe temporary extract path: $tmpDirFull"
        }
        if (Test-Path $tmpZip) { Remove-Item -LiteralPath $tmpZip -Force }
        if (Test-Path $tmpDir) { Remove-Item -LiteralPath $tmpDir -Recurse -Force }

        Write-Host "[~] Downloading PicoClaw $($release.tag_name)..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmpZip -UseBasicParsing
        Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

        $downloadedExe = Get-ChildItem -Path $tmpDir -Recurse -File |
            Where-Object { $_.Name -match "picoclaw.*\.exe$" } |
            Select-Object -First 1

        if (-not $downloadedExe) {
            throw "No PicoClaw executable found inside $tmpZip."
        }

        Copy-Item -Path $downloadedExe.FullName -Destination $PICOCLAW_EXE -Force
        Write-Host "[+] Downloaded to: $PICOCLAW_EXE" -ForegroundColor Green
    } catch {
        Write-Host "[!] Download failed: $_" -ForegroundColor Red
        Write-Host "    Download manually from: https://github.com/sipeed/picoclaw/releases/latest" -ForegroundColor Yellow
        Write-Host "    Place the binary at: $PICOCLAW_EXE" -ForegroundColor Yellow
        Write-Host "    Then re-run with -ConfigOnly flag." -ForegroundColor Yellow
    }
} else {
    Write-Host "[~] Skipping download (ConfigOnly mode)" -ForegroundColor Yellow
}

# 3. Copy config
$targetConfig = "$InstallDir\config.yaml"
if (Test-Path $PICOCLAW_CONFIG) {
    Copy-Item -Path $PICOCLAW_CONFIG -Destination $targetConfig -Force
    Write-Host "[+] Config copied to: $targetConfig" -ForegroundColor Green
} else {
    Write-Host "[!] Config not found at $PICOCLAW_CONFIG" -ForegroundColor Red
    Write-Host "    Run this script from the project root." -ForegroundColor Yellow
}

# 4. Create Windows scheduled task (auto-start at login)
$taskName = "IRIS-PicoClaw"
$taskExists = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($taskExists) {
    Write-Host "[~] Scheduled task '$taskName' already exists - skipping." -ForegroundColor Yellow
} elseif (Test-Path $PICOCLAW_EXE) {
    $action  = New-ScheduledTaskAction -Execute $PICOCLAW_EXE -Argument "--config `"$targetConfig`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3

    try {
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
            -Settings $settings -RunLevel Highest -Force | Out-Null
        Write-Host "[+] Scheduled task created: '$taskName' (starts at login)" -ForegroundColor Green
    } catch {
        Write-Host "[!] Could not create scheduled task: $_" -ForegroundColor Yellow
        Write-Host "    PicoClaw will still be started for this session." -ForegroundColor Yellow
    }
}

# 5. Start PicoClaw immediately
if (Test-Path $PICOCLAW_EXE) {
    Write-Host "[~] Starting PicoClaw..." -ForegroundColor Yellow
    Start-Process -FilePath $PICOCLAW_EXE -ArgumentList "--config `"$targetConfig`"" -WindowStyle Hidden
    Start-Sleep -Seconds 2

    try {
        $health = Invoke-RestMethod -Uri "http://localhost:8765/health" -TimeoutSec 5
        Write-Host "[+] PicoClaw running! Status: $($health.status)" -ForegroundColor Green
    } catch {
        Write-Host "[~] PicoClaw may still be starting - check http://localhost:8765/health" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Gateway : http://localhost:8765" -ForegroundColor White
Write-Host "  Health  : http://localhost:8765/health" -ForegroundColor White
Write-Host "  MCP call: POST http://localhost:8765/mcp/call" -ForegroundColor White
Write-Host ""
Write-Host "  Add your API keys to: $targetConfig" -ForegroundColor Yellow
Write-Host "  Then restart PicoClaw for changes to take effect." -ForegroundColor Yellow
Write-Host ""
