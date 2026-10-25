[CmdletBinding()]
param(
    [switch]$Force,
    [string]$Pilot = ''
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$secretPath = Join-Path (Join-Path $env:LOCALAPPDATA 'BuiltWhys') 'pexels.secrets.clixml'
if (-not (Test-Path -LiteralPath $secretPath)) {
    throw 'Pexels settings not found. Run setup_pexels.ps1 first.'
}

$settings = Import-Clixml -LiteralPath $secretPath
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($settings.ApiKey)
try {
    $env:PEXELS_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $generator = Join-Path $PSScriptRoot 'generate_pexels_batch.py'
    $arguments = @($generator)
    if ($Force) { $arguments += '--force' }
    if (-not [string]::IsNullOrWhiteSpace($Pilot)) { $arguments += @('--pilot', $Pilot) }
    Push-Location $projectRoot
    try {
        & python @arguments
        if ($LASTEXITCODE -ne 0) { throw "Pexels asset generation failed with exit code $LASTEXITCODE." }
    } finally {
        Pop-Location
    }
} finally {
    $env:PEXELS_API_KEY = $null
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}
