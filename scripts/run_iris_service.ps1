param(
    [Parameter(Mandatory = $true)]
    [string]$Title,

    [Parameter(Mandatory = $true)]
    [string]$WorkingDirectory,

    [Parameter(Mandatory = $true)]
    [string]$Executable,

    [Parameter(Mandatory = $true)]
    [string]$LogPath,

    [string]$ArgumentLine = '',

    [string]$EnvLine = ''
)

# Não usar 'Stop' — stderr de processos nativos vira ErrorRecord no PS pipeline
$ErrorActionPreference = 'Continue'

try { $Host.UI.RawUI.WindowTitle = $Title } catch {}

Set-Location -LiteralPath $WorkingDirectory

# Variáveis de ambiente
if ($EnvLine) {
    foreach ($pair in ($EnvLine -split '\|')) {
        if (-not $pair) { continue }
        $parts = $pair -split '=', 2
        if ($parts.Count -eq 2) {
            [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
        }
    }
}

$Arguments = if ($ArgumentLine) { $ArgumentLine -split '\|' } else { @() }

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null
[System.IO.File]::WriteAllText($LogPath, '', [System.Text.Encoding]::UTF8)

$exitCode = 0
try {
    # ── ProcessStartInfo: controle total sem problemas de ErrorRecord ──────
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName               = $Executable
    $psi.WorkingDirectory       = $WorkingDirectory
    $psi.UseShellExecute        = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
    $psi.Arguments = ($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ }
    }) -join ' '

    $psi.Environment['PYTHONUTF8']        = '1'
    $psi.Environment['PYTHONIOENCODING']  = 'utf-8'

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo             = $psi
    $process.EnableRaisingEvents   = $true

    # ── Handlers de log em tempo real via Register-ObjectEvent ─────────────
    $evtData  = @{ LogPath = $LogPath }
    $stdoutId = "IrisOut_$PID"
    $stderrId = "IrisErr_$PID"

    $null = Register-ObjectEvent -InputObject $process `
        -EventName 'OutputDataReceived' `
        -SourceIdentifier $stdoutId `
        -MessageData $evtData `
        -Action {
            if ($null -ne $Event.SourceEventArgs.Data) {
                $line = $Event.SourceEventArgs.Data
                [Console]::WriteLine($line)
                [System.IO.File]::AppendAllText(
                    $Event.MessageData.LogPath,
                    "$line`n",
                    [System.Text.Encoding]::UTF8
                )
            }
        }

    $null = Register-ObjectEvent -InputObject $process `
        -EventName 'ErrorDataReceived' `
        -SourceIdentifier $stderrId `
        -MessageData $evtData `
        -Action {
            if ($null -ne $Event.SourceEventArgs.Data) {
                $line = $Event.SourceEventArgs.Data
                [Console]::WriteLine($line)
                [System.IO.File]::AppendAllText(
                    $Event.MessageData.LogPath,
                    "$line`n",
                    [System.Text.Encoding]::UTF8
                )
            }
        }

    [void]$process.Start()
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()

    # Loop de polling: cede controle ao event pump do PS a cada 200ms
    # Isso permite que os Register-ObjectEvent -Action processem os eventos
    while (-not $process.HasExited) {
        Start-Sleep -Milliseconds 200
    }
    $process.WaitForExit()
    $exitCode = $process.ExitCode

} catch {
    $errMsg = $_ | Out-String
    [System.IO.File]::AppendAllText($LogPath, $errMsg, [System.Text.Encoding]::UTF8)
    Write-Host $errMsg -ForegroundColor Red
    $exitCode = 1
} finally {
    Unregister-Event -SourceIdentifier $stdoutId -ErrorAction SilentlyContinue
    Unregister-Event -SourceIdentifier $stderrId -ErrorAction SilentlyContinue
}

if ($exitCode -ne 0) {
    Write-Host ''
    Write-Host "[IRIS] $Title encerrou (exit $exitCode). Log: $LogPath" -ForegroundColor Yellow
    Read-Host 'Pressione Enter para fechar'
}

exit $exitCode
