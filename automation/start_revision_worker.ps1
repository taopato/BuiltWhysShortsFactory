[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$workerScript = Join-Path $PSScriptRoot 'revision_worker.py'
$logDirectory = Join-Path $projectRoot 'storage\logs'
$pidPath = Join-Path $logDirectory 'revision-worker.pid'
$stdoutPath = Join-Path $logDirectory 'revision-worker.out.log'
$stderrPath = Join-Path $logDirectory 'revision-worker.err.log'
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

if (Test-Path -LiteralPath $pidPath) {
    $existingPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
    if ($existingPid -match '^\d+$' -and (Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue)) {
        Write-Output "Revision worker is already running (PID $existingPid)."
        exit 0
    }
}

$process = Start-Process -FilePath 'python.exe' `
    -ArgumentList @($workerScript) `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru
Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii
Write-Output "Revision worker started (PID $($process.Id))."
