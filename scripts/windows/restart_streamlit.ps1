# restart_streamlit.ps1 — restart only the Streamlit frontend (v0.9.1)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $projectRoot

$venvPy = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $python = $venvPy } else { $python = "python" }

& $python -c "from services.remote_control import process_manager as PM; print(PM.restart_streamlit())"
