[CmdletBinding()]
param(
    [string]$OutputPath = (Join-Path (Split-Path $PSScriptRoot -Parent) '.env.automation'),
    [string]$Domain = '',
    [string]$AllowedEmail = '',
    [string]$LoginClientId = '',
    [Security.SecureString]$LoginClientSecret
)

$ErrorActionPreference = 'Stop'
$secretDirectory = Join-Path $env:LOCALAPPDATA 'BuiltWhys'

function Plain([Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

$telegramPath = Join-Path $secretDirectory 'telegram.secrets.clixml'
$pexelsPath = Join-Path $secretDirectory 'pexels.secrets.clixml'
$metaPath = Join-Path $secretDirectory 'meta.secrets.clixml'
foreach ($required in @($telegramPath, $pexelsPath, $metaPath)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Missing local secret setup: $required" }
}
$telegram = Import-Clixml -LiteralPath $telegramPath
$pexels = Import-Clixml -LiteralPath $pexelsPath
$meta = Import-Clixml -LiteralPath $metaPath
$domain = $Domain.Trim()
if ([string]::IsNullOrWhiteSpace($domain)) { $domain = (Read-Host 'Control Center domain (example: control.builtwhys.com)').Trim() }
if ([string]::IsNullOrWhiteSpace($domain)) { throw 'A domain is required for automatic HTTPS.' }
$allowedEmail = $AllowedEmail.Trim().ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($allowedEmail)) { $allowedEmail = (Read-Host 'Only allowed Google email').Trim().ToLowerInvariant() }
if ($allowedEmail -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') { throw 'A valid Google email is required.' }
$loginClientId = $LoginClientId.Trim()
if ([string]::IsNullOrWhiteSpace($loginClientId)) { $loginClientId = (Read-Host 'Control Center Google Web Client ID').Trim() }
if ([string]::IsNullOrWhiteSpace($loginClientId)) { throw 'Google Web Client ID is required.' }
$loginClientSecretPlain = if ($LoginClientSecret) { Plain $LoginClientSecret } else { Plain (Read-Host 'Control Center Google Web Client Secret' -AsSecureString) }
if ([string]::IsNullOrWhiteSpace($loginClientSecretPlain)) { throw 'Google Web Client Secret is required.' }

$random = New-Object byte[] 36
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($random) } finally { $rng.Dispose() }
$sessionSecret = [Convert]::ToBase64String($random).Replace('/', '_').Replace('+', '-').TrimEnd('=')
$values = [ordered]@{
    TELEGRAM_BOT_TOKEN = Plain $telegram.Token
    TELEGRAM_CHAT_ID = [string]$telegram.ChatId
    PEXELS_API_KEY = Plain $pexels.ApiKey
    CONTROL_CENTER_AUTH_MODE = 'google'
    CONTROL_CENTER_ALLOWED_EMAIL = $allowedEmail
    CONTROL_CENTER_SESSION_SECRET = $sessionSecret
    CONTROL_CENTER_GOOGLE_CLIENT_ID = $loginClientId
    CONTROL_CENTER_GOOGLE_CLIENT_SECRET = $loginClientSecretPlain
    CONTROL_CENTER_DOMAIN = $domain
    CONTROL_CENTER_PUBLIC_URL = "https://$domain"
    PUBLISH_ENABLED = 'false'
    META_PAGE_ACCESS_TOKEN = Plain $meta.PageAccessToken
    META_PAGE_ID = [string]$meta.PageId
    META_IG_USER_ID = [string]$meta.InstagramUserId
    META_GRAPH_VERSION = [string]$meta.GraphVersion
    GOOGLE_CLIENT_ID = ''
    GOOGLE_CLIENT_SECRET = ''
    GOOGLE_REFRESH_TOKEN = ''
    GOOGLE_DRIVE_FOLDER_ID = ''
    YOUTUBE_PRIVACY_STATUS = 'public'
    YOUTUBE_CATEGORY_ID = '28'
    YOUTUBE_DEFAULT_LANGUAGE = 'en'
    OLLAMA_MODEL = 'qwen3:4b'
}
$lines = @('# BuiltWhys production secrets. Never commit or share this file.')
$lines += $values.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }
[IO.File]::WriteAllLines($OutputPath, $lines, [Text.UTF8Encoding]::new($false))
Write-Host "Server environment written to: $OutputPath"
Write-Host "Control Center access is restricted to: $allowedEmail"
Write-Host 'Google client secret and session signing key were saved only in the uncommitted environment file.'
Write-Host 'Live publishing remains OFF.'
