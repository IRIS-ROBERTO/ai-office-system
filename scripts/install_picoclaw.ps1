# ============================================================================
# IRIS AI Office System - PicoClaw Gateway Installer
#
# PicoClaw current releases use:
#   - command: picoclaw gateway
#   - config:  ~/.picoclaw/config.json
#   - gateway: http://127.0.0.1:18790
#
# Usage:
#   .\scripts\install_picoclaw.ps1
#   .\scripts\install_picoclaw.ps1 -ConfigOnly
#   .\scripts\install_picoclaw.ps1 -OverwriteConfig
# ============================================================================

param(
    [switch]$ConfigOnly = $false,
    [switch]$OverwriteConfig = $false,
    [string]$InstallDir = "$env:LOCALAPPDATA\PicoClaw",
    [string]$PicoClawHome = "$env:USERPROFILE\.picoclaw",
    [string]$AITeamsRoot = "$env:USERPROFILE\Desktop\SUCESSOS!!!!!!!!!!!!!!!!!!!!!!!!!!\AIteams",
    [int]$GatewayPort = 18790
)

$ErrorActionPreference = "Stop"

$BundledConfig = Join-Path $PSScriptRoot "picoclaw_config.json"
$PicoClawExe = Join-Path $InstallDir "picoclaw.exe"
$TargetConfig = Join-Path $PicoClawHome "config.json"
$GatewayUrl = "http://127.0.0.1:$GatewayPort"
$OutLog = Join-Path $InstallDir "picoclaw-gateway.out.log"
$ErrLog = Join-Path $InstallDir "picoclaw-gateway.err.log"

Write-Host ""
Write-Host "=== IRIS PicoClaw Gateway Installer ===" -ForegroundColor Cyan
Write-Host ""

foreach ($dir in @($InstallDir, $PicoClawHome, $AITeamsRoot, (Join-Path $AITeamsRoot "_system\picoclaw"))) {
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "[+] Created directory: $dir" -ForegroundColor Green
    }
}

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
        if (Test-Path -LiteralPath $tmpZip) { Remove-Item -LiteralPath $tmpZip -Force }
        if (Test-Path -LiteralPath $tmpDir) { Remove-Item -LiteralPath $tmpDir -Recurse -Force }

        Write-Host "[~] Downloading PicoClaw $($release.tag_name)..." -ForegroundColor Yellow
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmpZip -UseBasicParsing
        Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

        $downloadedExe = Get-ChildItem -Path $tmpDir -Recurse -File -Filter "picoclaw.exe" |
            Where-Object { $_.Name -eq "picoclaw.exe" } |
            Sort-Object Length -Descending |
            Select-Object -First 1

        if (-not $downloadedExe) {
            $foundExecutables = Get-ChildItem -Path $tmpDir -Recurse -File -Filter "*.exe" |
                ForEach-Object { $_.Name } |
                Sort-Object
            throw "PicoClaw CLI executable picoclaw.exe not found inside $tmpZip. Found: $($foundExecutables -join ', ')"
        }

        Copy-Item -Path $downloadedExe.FullName -Destination $PicoClawExe -Force
        $installedSize = (Get-Item -LiteralPath $PicoClawExe).Length
        if ($installedSize -lt 10000000) {
            throw "Installed PicoClaw binary is unexpectedly small ($installedSize bytes). This usually means a launcher executable was selected instead of the CLI."
        }
        Write-Host "[+] Downloaded CLI to: $PicoClawExe ($installedSize bytes)" -ForegroundColor Green
    } catch {
        Write-Host "[!] Download failed: $_" -ForegroundColor Red
        Write-Host "    Download manually from: https://github.com/sipeed/picoclaw/releases/latest" -ForegroundColor Yellow
        Write-Host "    Place the binary at: $PicoClawExe" -ForegroundColor Yellow
        Write-Host "    Then re-run with -ConfigOnly." -ForegroundColor Yellow
    }
} else {
    Write-Host "[~] Skipping download (ConfigOnly mode)" -ForegroundColor Yellow
}

if (-not (Test-Path -LiteralPath $BundledConfig)) {
    throw "Bundled config not found: $BundledConfig"
}

if (Test-Path -LiteralPath $TargetConfig) {
    if ($OverwriteConfig) {
        $backup = "$TargetConfig.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
        Copy-Item -Path $TargetConfig -Destination $backup -Force
        Copy-Item -Path $BundledConfig -Destination $TargetConfig -Force
        Write-Host "[+] Existing config backed up to: $backup" -ForegroundColor Green
        Write-Host "[+] Config overwritten at: $TargetConfig" -ForegroundColor Green
    } else {
        Write-Host "[~] Existing config preserved: $TargetConfig" -ForegroundColor Yellow
        Write-Host "    Use -OverwriteConfig to replace it with the IRIS template." -ForegroundColor Yellow
    }
} else {
    Copy-Item -Path $BundledConfig -Destination $TargetConfig -Force
    Write-Host "[+] Config copied to: $TargetConfig" -ForegroundColor Green
}

$taskName = "IRIS-PicoClaw"
$taskExists = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
$taskArgs = "gateway"

if ($taskExists) {
    Write-Host "[~] Scheduled task '$taskName' already exists - updating action." -ForegroundColor Yellow
    $action = New-ScheduledTaskAction -Execute $PicoClawExe -Argument $taskArgs -WorkingDirectory $PicoClawHome
    Set-ScheduledTask -TaskName $taskName -Action $action | Out-Null
} elseif (Test-Path -LiteralPath $PicoClawExe) {
    $action = New-ScheduledTaskAction -Execute $PicoClawExe -Argument $taskArgs -WorkingDirectory $PicoClawHome
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 0) -RestartCount 3

    try {
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
            -Settings $settings -RunLevel Highest -Force | Out-Null
        Write-Host "[+] Scheduled task created: '$taskName' (starts at login)" -ForegroundColor Green
    } catch {
        Write-Host "[~] Elevated scheduled task failed: $_" -ForegroundColor Yellow
        Write-Host "    Retrying as current user without elevation." -ForegroundColor Yellow
        try {
            Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
                -Settings $settings -Force | Out-Null
            Write-Host "[+] Scheduled task created: '$taskName' (current user, starts at login)" -ForegroundColor Green
        } catch {
            Write-Host "[!] Could not create scheduled task: $_" -ForegroundColor Yellow
            Write-Host "    PicoClaw will still be started for this session." -ForegroundColor Yellow
        }
    }
}

if (Test-Path -LiteralPath $PicoClawExe) {
    Get-Process | Where-Object { $_.ProcessName -like "*picoclaw*" } | ForEach-Object {
        Stop-Process -Id $_.Id -Force
    }

    Write-Host "[~] Starting PicoClaw gateway..." -ForegroundColor Yellow
    $env:PICOCLAW_HOME = $PicoClawHome
    $env:PICOCLAW_CONFIG = $TargetConfig
    $env:PICOCLAW_GATEWAY_HOST = "127.0.0.1"
    $env:PICOCLAW_GATEWAY_PORT = "$GatewayPort"
    Start-Process -FilePath $PicoClawExe -ArgumentList @("gateway") `
        -WorkingDirectory $PicoClawHome `
        -RedirectStandardOutput $OutLog `
        -RedirectStandardError $ErrLog `
        -WindowStyle Hidden
    Start-Sleep -Seconds 5

    try {
        $health = Invoke-RestMethod -Uri "$GatewayUrl/health" -TimeoutSec 8
        Write-Host "[+] PicoClaw gateway running. Status: $($health.status)" -ForegroundColor Green
    } catch {
        Write-Host "[~] PicoClaw gateway did not answer $GatewayUrl/health yet." -ForegroundColor Yellow
        Write-Host "    stdout: $OutLog" -ForegroundColor Yellow
        Write-Host "    stderr: $ErrLog" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "=== Installation complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Home    : $PicoClawHome" -ForegroundColor White
Write-Host "  Config  : $TargetConfig" -ForegroundColor White
Write-Host "  Gateway : $GatewayUrl" -ForegroundColor White
Write-Host "  Health  : $GatewayUrl/health" -ForegroundColor White
Write-Host ""
Write-Host "  Store real credentials in .security.yml or your local config, not in git." -ForegroundColor Yellow
Write-Host ""
