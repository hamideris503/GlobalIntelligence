@echo off
REM Supervisor برای اجرای پایدار Backend روی Windows.
REM چرا لازم است: Task Scheduler با RestartCount/RestartInterval فرآیندی را که
REM با kill -9 یا crash می‌میرد دوباره اجرا نمی‌کند (آزمون واقعی: پس از kill،
REM سرویس برنگشت و LastTaskResult=1 شد). این wrapper حلقهٔ restart واقعی است.
REM
REM استفاده:  run_backend_forever.cmd [port] [python.exe]
REM آرگومان‌ها بدون quote پاس داده می‌شوند تا cmd.exe در Task Scheduler دچار خطای
REM تجزیهٔ quote نشود (آزمون واقعی: LastTaskResult=1 پیش از اجرای اسکریپت).
setlocal EnableExtensions

set "PORT=%~1"
set "PYEXE=%~2"
if "%PYEXE%"=="" set "PYEXE=.venv\Scripts\python.exe"
if "%PORT%"=="" set "PORT=8000"

set "ROOT=%~dp0.."
pushd "%ROOT%" || exit /b 1
if not exist "logs" mkdir "logs"
set "SUPLOG=logs\backend.supervisor.log"
REM لاگ هر نمونه جدا است تا دو فرآیند هم‌زمان روی یک فایل قفل نکنند.
set "OUTLOG=logs\backend-%PORT%.out.log"
set "ERRLOG=logs\backend-%PORT%.err.log"

REM در این ماشین 'timeout' به نسخهٔ GNU (Git) resolve می‌شد و حلقه می‌شکست؛
REM مسیر کامل نسخهٔ ویندوز استفاده می‌شود.
set "WAIT=%SystemRoot%\System32\timeout.exe"

:loop
if exist "logs\backend.stop" goto stopped
echo [%date% %time%] starting backend on port %PORT% >> "%SUPLOG%"
"%PYEXE%" -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT% >> "%OUTLOG%" 2>> "%ERRLOG%"
set "RC=%ERRORLEVEL%"
echo [%date% %time%] backend exited rc=%RC%; restarting in 5s >> "%SUPLOG%"
if exist "%WAIT%" (
  "%WAIT%" /t 5 /nobreak >nul 2>&1
) else (
  ping -n 6 127.0.0.1 >nul 2>&1
)
goto loop

:stopped
echo [%date% %time%] stop sentinel detected; supervisor exiting >> "%SUPLOG%"
del "logs\backend.stop" >nul 2>&1
endlocal
exit /b 0
