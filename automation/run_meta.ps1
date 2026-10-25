[CmdletBinding()]
param(
    [ValidateSet('verify', 'publish')]
    [string]$Mode = 'verify',
    [string]$JobId = '',
    [ValidateSet('facebook', 'instagram', 'both')]
    [string]$Platform = 'both',
    [string]$Metadata = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$publisherScript = Join-Path $PSScriptRoot 'meta_publish.py'
$secretPath = Join-Path (Join-Path $env:LOCALAPPDATA 'BuiltWhys') 'meta.secrets.clixml'
if (-not (Test-Path -LiteralPath $secretPath)) {
    throw 'Meta settings are missing. Run automation/setup_meta.ps1 first.'
}

$settings = Import-Clixml -LiteralPath $secretPath
$pointers = @()
function Set-SecretEnvironment([string]$Name, [Security.SecureString]$Value) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    $script:pointers += $pointer
    Set-Item -Path "Env:$Name" -Value ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer))
}

try {
    Set-SecretEnvironment 'META_PAGE_ACCESS_TOKEN' $settings.PageAccessToken
    $env:META_PAGE_ID = [string]$settings.PageId
    $env:META_IG_USER_ID = [string]$settings.InstagramUserId
    $env:META_GRAPH_VERSION = [string]$settings.GraphVersion
    Push-Location -LiteralPath $projectRoot
    if ($Mode -eq 'verify') {
        python $publisherScript verify
    } else {
        if ([string]::IsNullOrWhiteSpace($JobId)) { throw 'JobId is required in publish mode.' }
        $arguments = @($publisherScript, 'publish', $JobId, '--platform', $Platform)
        if (-not [string]::IsNullOrWhiteSpace($Metadata)) { $arguments += @('--metadata', $Metadata) }
        python @arguments
    }
} finally {
    Pop-Location -ErrorAction SilentlyContinue
    Remove-Item Env:META_PAGE_ACCESS_TOKEN, Env:META_PAGE_ID, Env:META_IG_USER_ID, Env:META_GRAPH_VERSION -ErrorAction SilentlyContinue
    foreach ($pointer in $pointers) {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    }
}
