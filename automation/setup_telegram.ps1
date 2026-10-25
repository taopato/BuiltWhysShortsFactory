[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path $env:LOCALAPPDATA 'BuiltWhys'
$secretPath = Join-Path $secretDirectory 'telegram.secrets.clixml'

Write-Host 'Create a bot with @BotFather, then send the new bot one message.'
$token = Read-Host 'Telegram bot token' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($token)
try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $bot = Invoke-RestMethod -Method Get -Uri "https://api.telegram.org/bot$plainToken/getMe"
    if (-not $bot.ok) { throw 'Telegram rejected the bot token.' }
    Write-Host "Connected to @$($bot.result.username). Open this bot, press Start, and send any message."

    $deadline = (Get-Date).AddSeconds(60)
    $chats = @()
    do {
        $response = Invoke-RestMethod -Method Get -Uri "https://api.telegram.org/bot$plainToken/getUpdates"
        $chats = @($response.result |
            ForEach-Object {
                if ($_.message.chat) { $_.message.chat }
                elseif ($_.callback_query.message.chat) { $_.callback_query.message.chat }
            } |
            Where-Object { $_ -and $_.type -eq 'private' } |
            Sort-Object id -Unique)
        if ($chats.Count -eq 0) { Start-Sleep -Seconds 3 }
    } while ($chats.Count -eq 0 -and (Get-Date) -lt $deadline)
} finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $plainToken = $null
}

if ($chats.Count -eq 0) {
    throw 'No private chat found. Open the bot, press Start, send it a message, then run setup again.'
}
if ($chats.Count -eq 1) {
    $chatId = [string]$chats[0].id
    Write-Host "Found Telegram chat: $($chats[0].first_name) ($chatId)"
} else {
    $chats | Select-Object id, username, first_name | Format-Table -AutoSize
    $chatId = Read-Host 'Enter your chat ID from the table'
}
if ([string]::IsNullOrWhiteSpace($chatId)) { throw 'Chat ID cannot be empty.' }

New-Item -ItemType Directory -Force -Path $secretDirectory | Out-Null
[PSCustomObject]@{ Token = $token; ChatId = $chatId.Trim() } |
    Export-Clixml -LiteralPath $secretPath
Write-Host "Telegram settings were encrypted for the current Windows user: $secretPath"
