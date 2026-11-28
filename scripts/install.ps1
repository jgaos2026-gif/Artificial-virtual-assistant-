[CmdletBinding()]
param(
    [string]$Source = (Split-Path -Parent $PSScriptRoot),
    [string]$Runtime = (Join-Path $env:USERPROFILE "JGA\OASIS-Research-Runtime")
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Source = [System.IO.Path]::GetFullPath($Source)
$Runtime = [System.IO.Path]::GetFullPath($Runtime)

if (-not (Test-Path -LiteralPath (Join-Path $Source "pyproject.toml") -PathType Leaf)) {
    throw "Source path is not an AVA Python project: $Source"
}
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { throw "Python 3.11+ is required. Install Python, then rerun this script." }
$version = & $python.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or [version]$version -lt [version]"3.11") {
    throw "Python 3.11 or newer is required. Found: $version"
}

if (Test-Path -LiteralPath $Runtime) {
    $items = @(Get-ChildItem -LiteralPath $Runtime -Force)
    if ($items.Count -gt 0) {
        throw "Refusing to overwrite non-empty runtime directory: $Runtime. Back up and inspect it; this installer will not reset it."
    }
} else {
    New-Item -ItemType Directory -Path $Runtime | Out-Null
}

$venv = Join-Path $Runtime ".venv"
if (-not (Test-Path -LiteralPath $venv)) {
    & $python.Source -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
}
$venvPython = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) { throw "Expected Windows venv interpreter is missing: $venvPython" }

& $venvPython -m pip install --no-deps -e $Source
if ($LASTEXITCODE -ne 0) { throw "Editable package installation failed. Runtime directory was not deleted." }

$doctor = & $venvPython -m ava_military.doctor --source $Source --runtime $Runtime
if ($LASTEXITCODE -ne 0) { throw "Post-install doctor reported blockers: $doctor" }
$doctor | Set-Content -LiteralPath (Join-Path $Runtime "foundation-doctor.json") -Encoding utf8
Write-Host "AVA research foundation installed. This is NOT the integrated AVA/OASIS runtime."
Write-Host "Runtime: $Runtime"
Write-Host "Doctor report: $(Join-Path $Runtime 'foundation-doctor.json')"
Write-Host "No Windows service, firewall rule, listener, model, or privileged component was installed."
