Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Write-Host "Starting Windows setup for Python environment..."
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Repository root: $repoRoot"

$venvPython = @("python")
$pyCmd = Get-Command py -ErrorAction SilentlyContinue
if ($null -ne $pyCmd) {
    $candidates = @(
        @("py", "-3.12"),
        @("py", "-3.11")
    )
    foreach ($cand in $candidates) {
        & $cand[0] $cand[1] -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" *> $null
        if ($LASTEXITCODE -eq 0) {
            $venvPython = $cand
            break
        }
    }
}

if (Test-Path "$repoRoot\venv") {
    Write-Host "Virtual environment already exists at $repoRoot\venv"
} else {
    Write-Host "Creating virtual environment..."
    if ($venvPython.Length -ge 2) {
        & $venvPython[0] $venvPython[1] -m venv "$repoRoot\venv"
    } else {
        & $venvPython[0] -m venv "$repoRoot\venv"
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$repoRoot\venv")) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
    Write-Host "Virtual environment created."
}
Write-Host "Activating virtual environment..."
$activatePath = Join-Path "$repoRoot\venv\Scripts" "Activate.ps1"
if (-not (Test-Path $activatePath)) {
    Write-Error "Activation script not found at $activatePath"
    exit 1
}
. $activatePath
if (-not $env:VIRTUAL_ENV) {
    Write-Error "Virtual environment activation failed."
    exit 1
}
Write-Host "Activated: $env:VIRTUAL_ENV"
$pythonExe = Join-Path "$repoRoot\venv\Scripts" "python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Error "Python executable not found at $pythonExe"
    exit 1
}

Write-Host "Ensuring pip is available in the virtual environment..."
& $pythonExe -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip not found. Bootstrapping via ensurepip..."
    & $pythonExe -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to bootstrap pip. Delete the venv folder and re-run setup_windows.ps1."
        exit 1
    }
}

$minorText = & $pythonExe -c "import sys; print(sys.version_info.minor)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to detect Python version from venv."
    exit 1
}
$minor = [int]$minorText
if ($minor -ge 13) {
    Write-Error "Python 3.$minor detected in the venv. Use Python 3.11 or 3.12 for this project to avoid Rust-based builds of dependencies. Delete the venv folder and re-run setup after installing Python 3.12."
    exit 1
}

Write-Host "Upgrading pip..."
& $pythonExe -m pip install --upgrade pip --no-input
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip upgrade skipped."
}
$requirements = Join-Path $repoRoot "amplify\functions\modernization-handler\requirements.txt"
if (-not (Test-Path $requirements)) {
    Write-Error "Requirements file not found at $requirements"
    exit 1
}
Write-Host "Installing dependencies from $requirements ..."
& $pythonExe -m pip install -r $requirements --no-input
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dependency installation failed."
    exit 1
}
Write-Host "Setup completed successfully."
