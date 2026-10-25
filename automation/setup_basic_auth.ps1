[CmdletBinding()]
param(
    [string]$Email = 'ttarikcetinturk@gmail.com',
    [string]$EnvPath = '',
    [string]$Server = 'builtwhys@65.109.139.24',
    [string]$RemoteRoot = '/opt/builtwhys'
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($EnvPath)) {
    $EnvPath = Join-Path (Split-Path $scriptDirectory -Parent) '.env.automation'
}

function Convert-ToPlainText([Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}

function Convert-ToHex([byte[]]$Bytes) {
    return (($Bytes | ForEach-Object { $_.ToString('x2') }) -join '')
}

function Set-EnvValue([Collections.Generic.List[string]]$Lines, [string]$Key, [string]$Value) {
    $prefix = "$Key="
    for ($index = 0; $index -lt $Lines.Count; $index++) {
        if ($Lines[$index].StartsWith($prefix, [StringComparison]::Ordinal)) {
            $Lines[$index] = "$prefix$Value"
            return
        }
    }
    $Lines.Add("$prefix$Value")
}

if (-not (Test-Path -LiteralPath $EnvPath)) { throw "Environment file not found: $EnvPath" }
if ($Email -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') { throw 'A valid e-mail address is required.' }
$securePassword = Read-Host 'Control Center password' -AsSecureString
$password = Convert-ToPlainText $securePassword
if ($password.Length -lt 8) { throw 'Use a password with at least 8 characters.' }

$salt = New-Object byte[] 16
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
try { $rng.GetBytes($salt) } finally { $rng.Dispose() }
$iterations = 310000
$derive = [Security.Cryptography.Rfc2898DeriveBytes]::new(
    $password, $salt, $iterations, [Security.Cryptography.HashAlgorithmName]::SHA256
)
try { $digest = $derive.GetBytes(32) } finally { $derive.Dispose(); $password = $null }
$encodedHash = "pbkdf2_sha256`$$iterations`$$(Convert-ToHex $salt)`$$(Convert-ToHex $digest)"

$lines = [Collections.Generic.List[string]]::new()
$lines.AddRange([string[]][IO.File]::ReadAllLines($EnvPath))
Set-EnvValue $lines 'CONTROL_CENTER_AUTH_MODE' 'basic'
Set-EnvValue $lines 'CONTROL_CENTER_USER' $Email.Trim().ToLowerInvariant()
Set-EnvValue $lines 'CONTROL_CENTER_PASSWORD_HASH' $encodedHash
Set-EnvValue $lines 'CONTROL_CENTER_PASSWORD' ''
Set-EnvValue $lines 'CONTROL_CENTER_GOOGLE_CLIENT_ID' ''
Set-EnvValue $lines 'CONTROL_CENTER_GOOGLE_CLIENT_SECRET' ''
[IO.File]::WriteAllLines($EnvPath, $lines, [Text.UTF8Encoding]::new($false))

& scp $EnvPath "${Server}:${RemoteRoot}/.env.automation"
if ($LASTEXITCODE -ne 0) { throw 'Could not copy the environment file to the server.' }
& ssh $Server "chmod 600 ${RemoteRoot}/.env.automation && cd ${RemoteRoot} && docker compose --env-file .env.automation -f docker-compose.production.yml up -d --force-recreate control-center caddy"
if ($LASTEXITCODE -ne 0) { throw 'The Control Center services could not be restarted.' }

Write-Host "Control Center login was installed for $Email."
Write-Host 'Only a salted PBKDF2 password hash was stored; the password itself was not saved.'
