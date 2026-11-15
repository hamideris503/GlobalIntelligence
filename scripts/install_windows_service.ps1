<#
.SYNOPSIS
    GlobalIntelligence — اجرای پایدار ۲۴/۷ روی Windows (WP-16).

.DESCRIPTION
    یک Task Scheduler task برای اجرای Backend در Startup و پس از crash ثبت می‌کند.
    پیش‌فرض این اسکریپت DRY-RUN است: فقط دستورهای برنامه‌ریزی‌شده را چاپ می‌کند و
    هیچ تغییری در سیستم ایجاد نمی‌کند. برای نصب واقعی باید -Install بدهید و
    (به‌دلیل ثبت در Startup) PowerShell را با دسترسی Administrator اجرا کنید.

    هیچ secret داخل task نوشته نمی‌شود: تنظیمات از .env محل پروژه خوانده می‌شود.

.PARAMETER Action
    Plan (پیش‌فرض) | Install | Uninstall | Status

.PARAMETER Port
    پورت Backend (پیش‌فرض 8000)

.PARAMETER PythonExe
    مسیر python.exe (پیش‌فرض .venv\Scripts\python.exe در ریشهٔ پروژه)

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1
    powershell -ExecutionPolicy Bypass -File scripts\install_windows_service.ps1 -Action Install
#>
[CmdletBinding()]
param(
    [ValidateSet('Plan', 'Install', 'Stop', 'Start', 'Uninstall', 'Status')]
    [string]$Action = 'Plan',
    [int]$Port = 8000,
    [string]$PythonExe = '',
    [string]$TaskName = 'GlobalIntelligence-Backend',
    [string]$ProjectRoot = ''
)

$ErrorActionPreference = 'Stop'

if (-not $ProjectRoot) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}
if (-not $PythonExe) {
    $PythonExe = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
}

$LogDir = Join-Path $ProjectRoot 'logs'
$OutLog = Join-Path $LogDir 'backend.out.log'
$ErrLog = Join-Path $LogDir 'backend.err.log'
$SupervisorLog = Join-Path $LogDir 'backend.supervisor.log'
$HealthUrl = "http://127.0.0.1:$Port/health"

function Show-Plan {
    Write-Host '== GlobalIntelligence 24/7 plan (dry-run) ==' -ForegroundColor Cyan
    Write-Host "ProjectRoot : $ProjectRoot"
    Write-Host "Python      : $PythonExe"
    Write-Host "Port        : $Port"
    Write-Host "Task        : $TaskName"
    Write-Host "Logs        : $OutLog / $ErrLog / $SupervisorLog"
    Write-Host ''
    Write-Host 'Planned task action (supervisor wrapper):'
    Write-Host "  cmd.exe /c scripts\run_backend_forever.cmd $Port   (python: $PythonExe)"
    Write-Host '  (wrapper: restart real 5s after any crash/kill — Task Scheduler RestartCount alone did not restart a killed process)'
    Write-Host ''
    Write-Host 'Planned triggers/settings:'
    Write-Host '  - At startup (machine) or at logon (user)'
    Write-Host '  - Restart on failure: every 1 minute, up to 999 times'
    Write-Host '  - Start when available; do not stop on idle; no time limit'
    Write-Host '  - WorkingDirectory = ProjectRoot (so .env and dev.db resolve)'
    Write-Host ''
    Write-Host 'Nothing was changed. Re-run with -Action Install to apply.' -ForegroundColor Yellow
}

function Invoke-Install {
    if (-not (Test-Path $PythonExe)) {
        throw "Python executable not found: $PythonExe (create the venv first)"
    }
    if (-not (Test-Path (Join-Path $ProjectRoot '.env'))) {
        Write-Warning '.env not found — the service will fail the production guard on startup.'
    }
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

    $wrapper = Join-Path $ProjectRoot 'scripts\run_backend_forever.cmd'
    if (-not (Test-Path $wrapper)) {
        throw "Supervisor wrapper not found: $wrapper"
    }
    # Task Scheduler's RestartCount does NOT restart a killed process (verified: kill -9
    # left the service down with LastTaskResult=1). The cmd wrapper owns the restart loop;
    # the scheduler still guarantees "at startup".
    # مسیر کامل cmd.exe لازم است: در نشست Task Scheduler، PATH کوتاه‌شده است و
    # اجرای 'cmd.exe' با LastTaskResult=1 بلافاصله شکست می‌خورد (آزمون واقعی).
    $cmdExe = Join-Path $env:SystemRoot 'System32\cmd.exe'
    # آرگومان‌ها بدون کوتیشن پاس داده می‌شوند: cmd.exe در نشست Task Scheduler با
    # ترکیب "/c \"path\" \"path\" port" خطای تجزیه می‌دهد (LastTaskResult=1).
    if ($wrapper -match '\s') {
        throw "Project path contains spaces ($wrapper); adjust the task arguments manually."
    }
    $action = New-ScheduledTaskAction -Execute $cmdExe `
        -Argument "/c $wrapper $Port" `
        -WorkingDirectory $ProjectRoot
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
        -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Days 365)
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Highest

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Installed scheduled task '$TaskName'." -ForegroundColor Green
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Started. Health check: $HealthUrl"
}

function Stop-BackendProcesses {
    # Stop-ScheduledTask تنها فرزند مستقیم (cmd) را می‌بندد و python زنده می‌ماند.
    # ابتدا سنتینل stop ساخته می‌شود تا supervisor حلقه را ترک کند، سپس درخت فرآیند بسته می‌شود.
    $stopFile = Join-Path $LogDir 'backend.stop'
    New-Item -ItemType File -Force -Path $stopFile | Out-Null
    $targets = Get-CimInstance Win32_Process | Where-Object {
        ($_.CommandLine -and $_.CommandLine -like '*run_backend_forever.cmd*' -and $_.CommandLine -like "*$Port*") -or
        ($_.CommandLine -and $_.Name -eq 'python.exe' -and $_.CommandLine -like '*uvicorn*' -and $_.CommandLine -like "*--port $Port*")
    }
    foreach ($t in $targets) {
        try { Stop-Process -Id $t.ProcessId -Force -ErrorAction Stop; Write-Host "stopped PID $($t.ProcessId) $($t.Name)" } catch {}
    }
    Start-Sleep -Seconds 2
    if (Test-Path $stopFile) { Remove-Item $stopFile -Force -ErrorAction SilentlyContinue }
}

function Invoke-Stop {
    Stop-BackendProcesses
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host 'Stopped (task + supervisor + backend).' -ForegroundColor Green
}

function Invoke-Uninstall {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) { Write-Host "Task '$TaskName' not found."; return }
    Stop-BackendProcesses
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'." -ForegroundColor Green
}

function Show-Status {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $task) { Write-Host "Task '$TaskName': NOT INSTALLED"; return }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "Task      : $($task.TaskName) [$($task.State)]"
    Write-Host "Last run  : $($info.LastRunTime)  Result: $($info.LastTaskResult)"
    Write-Host "Next run  : $($info.NextRunTime)"
    try {
        $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 5
        Write-Host "Health    : $($health.status)" -ForegroundColor Green
    } catch {
        Write-Host "Health    : UNREACHABLE ($HealthUrl)" -ForegroundColor Yellow
    }
}

switch ($Action) {
    'Plan' { Show-Plan }
    'Install' { Invoke-Install }
    'Stop' { Invoke-Stop }
    'Start' {
        $stopFile = Join-Path $LogDir 'backend.stop'
        if (Test-Path $stopFile) { Remove-Item $stopFile -Force }
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Started. Health check: $HealthUrl"
    }
    'Uninstall' { Invoke-Uninstall }
    'Status' { Show-Status }
}
