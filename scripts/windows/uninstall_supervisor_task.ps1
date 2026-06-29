# uninstall_supervisor_task.ps1 — remove the supervisor scheduled task (v0.9.1)
$ErrorActionPreference = "Stop"
$taskName = "SeoulRecordsSupervisor"
try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Task '$taskName' removed."
} catch {
    Write-Host "Task '$taskName' not found or already removed."
}
