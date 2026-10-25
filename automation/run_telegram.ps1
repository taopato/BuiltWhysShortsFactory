[CmdletBinding()]
param(
    [ValidateSet('poll', 'send', 'sync', 'ping')]
    [string]$Mode = 'poll',
    [string]$JobId = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$reviewScript = Join-Path $PSScriptRoot 'review_queue.py'
$secretPath = Join-Path (Join-Path $env:LOCALAPPDATA 'BuiltWhys') 'telegram.secrets.clixml'
if (-not (Test-Path -LiteralPath $secretPath)) {
    throw 'Telegram settings are missing. Run automation/setup_telegram.ps1 first.'
}

$settings = Import-Clixml -LiteralPath $secretPath
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($settings.Token)
try {
    $env:TELEGRAM_BOT_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $env:TELEGRAM_CHAT_ID = [string]$settings.ChatId
    Push-Location -LiteralPath $projectRoot
    if ($Mode -in @('send', 'sync')) {
        if ([string]::IsNullOrWhiteSpace($JobId)) { throw 'JobId is required in send mode.' }
        python $reviewScript $Mode $JobId
    } elseif ($Mode -eq 'ping') {
        python $reviewScript ping
    } else {
        python $reviewScript poll
    }
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    Remove-Item Env:TELEGRAM_BOT_TOKEN -ErrorAction SilentlyContinue
    Remove-Item Env:TELEGRAM_CHAT_ID -ErrorAction SilentlyContinue
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}
