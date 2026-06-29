# start_studio_supervisor.ps1 — launch the Seoul Records supervisor (v0.9.1)
# Runs the supervisor + Telegram control bot in this window.
# No admin required.

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

# Prefer the project venv python if present
$venvPy = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $python = $venvPy
} else {
    $python = "python"
}

Write-Host "Seoul Records Supervisor 시작..."
Write-Host "Project: $projectRoot"
Write-Host "Python:  $python"

& $python -m workers.studio_supervisor_worker
