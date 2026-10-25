[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$runScript = Join-Path $PSScriptRoot 'run_telegram.ps1'
$logDirectory = Join-Path $projectRoot 'storage\logs'
$pidPath = Join-Path $logDirectory 'telegram-bot.pid'
$stdoutPath = Join-Path $logDirectory 'telegram-bot.out.log'
$stderrPath = Join-Path $logDirectory 'telegram-bot.err.log'

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

if (Test-Path -LiteralPath $pidPath) {
    $existingPid = (Get-Content -LiteralPath $pidPath -Raw).Trim()
    if ($existingPid -match '^\d+$') {
        $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
        if ($null -ne $existingProcess) {
            Write-Output "Telegram approval bot is already running (PID $existingPid)."
            exit 0
        }
    }
}

$arguments = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', $runScript,
    '-Mode', 'poll'
)
$process = Start-Process -FilePath 'powershell.exe' `
    -ArgumentList $arguments `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutPath `
    -RedirectStandardError $stderrPath `
    -PassThru

Set-Content -LiteralPath $pidPath -Value $process.Id -Encoding ascii
Write-Output "Telegram approval bot started (PID $($process.Id))."
