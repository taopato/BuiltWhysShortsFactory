[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$secureToken = Read-Host 'Telegram bot token' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $response = Invoke-RestMethod -Method Get -Uri "https://api.telegram.org/bot$token/getUpdates"
    $chats = $response.result |
        ForEach-Object {
            if ($_.message.chat) { $_.message.chat }
            elseif ($_.callback_query.message.chat) { $_.callback_query.message.chat }
        } |
        Where-Object { $_ } |
        Sort-Object id -Unique
    if (-not $chats) {
        Write-Host 'No chat found. Send the bot a message and run this script again.'
    } else {
        $chats | Select-Object id, type, username, first_name | Format-Table -AutoSize
    }
} finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $token = $null
}
