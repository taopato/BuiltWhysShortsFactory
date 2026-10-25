[CmdletBinding()]
param(
    [string]$EnvPath = '',
    [string]$Server = 'builtwhys@65.109.139.24',
    [string]$RemoteRoot = '/opt/builtwhys'
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path $scriptDirectory -Parent
if ([string]::IsNullOrWhiteSpace($EnvPath)) {
    $EnvPath = Join-Path $projectRoot '.env.automation'
}
if (-not (Test-Path -LiteralPath $EnvPath)) { throw "Environment file not found: $EnvPath" }

Push-Location $projectRoot
try {
    & python (Join-Path $scriptDirectory 'setup_google_oauth.py') --env-file $EnvPath
    if ($LASTEXITCODE -ne 0) { throw 'Google authorization was not completed.' }
    & scp $EnvPath "${Server}:${RemoteRoot}/.env.automation"
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy Google settings to the server.' }
    & ssh $Server "chmod 600 ${RemoteRoot}/.env.automation && cd ${RemoteRoot} && docker compose --env-file .env.automation -f docker-compose.production.yml up -d --force-recreate publisher-worker analytics-worker drive-archive-worker && python3 automation/preflight.py --env-file .env.automation --online"
    if ($LASTEXITCODE -ne 0) { throw 'Server verification failed; live publishing remains disabled.' }
} finally {
    Pop-Location
}

Write-Host 'YouTube, Analytics and Drive authorization is installed on the server.'
Write-Host 'Live publishing remains OFF until the private upload test passes.'
