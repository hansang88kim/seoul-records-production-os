# Windows Supervisor Setup (v0.9.1)

The supervisor watches the Streamlit frontend and restarts it if it crashes. It
runs as a **separate process** so it survives a frontend crash, and can be
registered as a per-user scheduled task so it starts automatically at logon.

## Run it manually

```
python -m workers.studio_supervisor_worker
```

It writes:

- `outputs/remote_control/supervisor_status.json`
- `outputs/remote_control/supervisor_log.jsonl`

## Install as a scheduled task (no admin required)

From PowerShell, in the project folder:

```
powershell -ExecutionPolicy Bypass -File scripts\windows\install_supervisor_task.ps1
```

This registers a task named **SeoulRecordsSupervisor** that runs
`start_studio_supervisor.ps1` at user logon.

Check it:

```
Get-ScheduledTask -TaskName SeoulRecordsSupervisor
Start-ScheduledTask -TaskName SeoulRecordsSupervisor   # start now
```

Uninstall:

```
powershell -ExecutionPolicy Bypass -File scripts\windows\uninstall_supervisor_task.ps1
```

## Restart loop guard

The supervisor restarts Streamlit at most `MAX_RESTARTS_PER_HOUR` (default 5)
times per hour. If the limit is hit it goes **degraded** and stops restarting,
so a broken app can't cause an endless restart loop.

## Configuration (environment variables)

- `STREAMLIT_PORT` (default 8501)
- `STREAMLIT_ADDRESS` (default 127.0.0.1)
- `HEALTH_CHECK_INTERVAL_SECONDS` (default 30)
- `MAX_RESTARTS_PER_HOUR` (default 5)
- `AUTO_RESTART_STREAMLIT` (default true)

## What it can and cannot recover

**Can recover (PC online):**
- Streamlit crashed or stopped responding on its port
- Frontend needs a remote restart while the PC is on

**Cannot recover:**
- PC powered off or asleep without wake support
- Internet or router down
- Windows account locked so the task cannot run
- Telegram blocked or network unavailable

## Recommended hardware/OS settings

- Disable sleep while rendering (or set a long sleep timer)
- BIOS: "restore on AC power loss" so the PC powers back on after an outage
- Optional smart plug to power-cycle remotely
- Optional Wake-on-LAN
- Keep Tailscale running at startup
