[CmdletBinding()]
param(
    [string]$EnvPath = (Join-Path (Split-Path $PSScriptRoot -Parent) '.env.automation'),
    [string]$Server = 'builtwhys@65.109.139.24',
    [string]$RemoteRoot = '/opt/builtwhys'
)

$ErrorActionPreference = 'Stop'

function Convert-ToPlainText([Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
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
$clientId = (Read-Host 'Google Web application Client ID').Trim()
$clientSecret = Convert-ToPlainText (Read-Host 'Google Web application Client Secret' -AsSecureString)
if ([string]::IsNullOrWhiteSpace($clientId) -or [string]::IsNullOrWhiteSpace($clientSecret)) {
    throw 'Client ID and Client Secret are required.'
}

$lines = [Collections.Generic.List[string]]::new()
$lines.AddRange([string[]][IO.File]::ReadAllLines($EnvPath))
Set-EnvValue $lines 'CONTROL_CENTER_GOOGLE_CLIENT_ID' $clientId
Set-EnvValue $lines 'CONTROL_CENTER_GOOGLE_CLIENT_SECRET' $clientSecret
[IO.File]::WriteAllLines($EnvPath, $lines, [Text.UTF8Encoding]::new($false))

& scp $EnvPath "${Server}:${RemoteRoot}/.env.automation"
if ($LASTEXITCODE -ne 0) { throw 'Could not copy the environment file to the server.' }
& ssh $Server "chmod 600 ${RemoteRoot}/.env.automation && cd ${RemoteRoot} && docker compose --env-file .env.automation -f docker-compose.production.yml up -d --force-recreate control-center caddy"
if ($LASTEXITCODE -ne 0) { throw 'The Control Center services could not be restarted.' }

Write-Host 'Google login settings were securely installed and Control Center was restarted.'
Write-Host 'The client secret was not printed or written into the project source.'
