# install_supervisor_task.ps1 — register the supervisor as a scheduled task (v0.9.1)
# Runs at user logon. No admin required for a per-user logon task.
# Task name: SeoulRecordsSupervisor

$ErrorActionPreference = "Stop"
$taskName = "SeoulRecordsSupervisor"
$projectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$startScript = Join-Path $PSScriptRoot "start_studio_supervisor.ps1"

Write-Host "Registering scheduled task '$taskName'..."
Write-Host "Start script: $startScript"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`""

# Run at logon for the current user
$trigger = New-ScheduledTaskTrigger -AtLogOn

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Description "Seoul Records Studio Supervisor" -Force
    Write-Host "Task '$taskName' registered. It will start at next logon."
    Write-Host "To start it now: Start-ScheduledTask -TaskName $taskName"
} catch {
    Write-Error "Failed to register task: $_"
}
