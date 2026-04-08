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

$ErrorActionPreference = 'Stop'

try {
    $Host.UI.RawUI.WindowTitle = $Title
} catch {}

Set-Location -LiteralPath $WorkingDirectory

if ($EnvLine) {
    $envPairs = $EnvLine -split '\|'
} else {
    $envPairs = @()
}

foreach ($pair in $envPairs) {
    if (-not $pair) { continue }
    $parts = $pair -split '=', 2
    if ($parts.Count -eq 2) {
        [Environment]::SetEnvironmentVariable($parts[0], $parts[1], 'Process')
    }
}

if ($ArgumentLine) {
    $Arguments = $ArgumentLine -split '\|'
} else {
    $Arguments = @()
}

New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null

try {
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $Executable
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $psi.Arguments = ($Arguments | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\"') + '"'
        } else {
            $_
        }
    }) -join ' '

    foreach ($pair in $envPairs) {
        if (-not $pair) { continue }
        $parts = $pair -split '=', 2
        if ($parts.Count -eq 2) {
            $psi.Environment[$parts[0]] = $parts[1]
        }
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    [void]$process.Start()

    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()

    $combinedOutput = ($stdoutTask.Result + $stderrTask.Result).Trim()
    if ($combinedOutput) {
        Add-Content -Path $LogPath -Value $combinedOutput
    }

    $exitCode = $process.ExitCode
} catch {
    $_ | Out-String | Add-Content -Path $LogPath
    $exitCode = 1
}

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "[IRIS] $Title encerrou com erro. Consulte $LogPath"
    Read-Host "Pressione Enter para fechar"
}

exit $exitCode
