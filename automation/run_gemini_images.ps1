[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$secretPath = Join-Path (Join-Path $env:LOCALAPPDATA 'BuiltWhys') 'gemini.secrets.clixml'
if (-not (Test-Path -LiteralPath $secretPath)) {
    throw "Gemini settings not found. Run setup_gemini.ps1 first."
}

$settings = Import-Clixml -LiteralPath $secretPath
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($settings.ApiKey)
try {
    $env:GEMINI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $generator = Join-Path $PSScriptRoot 'generate_gemini_batch.py'
    $arguments = @($generator, '--model', [string]$settings.Model)
    if ($Force) { $arguments += '--force' }
    Push-Location $projectRoot
    try {
        & python @arguments
    } finally {
        Pop-Location
    }
    if ($LASTEXITCODE -ne 0) { throw "Gemini image generation failed with exit code $LASTEXITCODE." }
} finally {
    $env:GEMINI_API_KEY = $null
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}
