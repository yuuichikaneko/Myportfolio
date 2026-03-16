@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

for /f %%P in ('powershell -NoProfile -Command "$start=5173; $end=5200; for($p=$start; $p -le $end; $p++){ $l=$null; try { $l=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,$p); $l.Start(); $l.Stop(); Write-Output $p; break } catch { if($l){$l.Stop()} } }"') do set FRONTEND_PORT=%%P

if "%FRONTEND_PORT%"=="" (
	echo Failed to find free frontend port in range 5173-5200.
	pause
	exit /b 1
)

echo ============================================================
echo Django + Frontend Startup
echo ============================================================
echo.

echo [1] Starting Django on port 8001...
set PYTHON_EXE=%~dp0\.venv\Scripts\python.exe
if exist "%PYTHON_EXE%" (
	start "Django - Port 8001" cmd /k "cd django && %PYTHON_EXE% manage.py runserver 8001"
) else (
	start "Django - Port 8001" cmd /k "cd django && py manage.py runserver 8001"
)

timeout /t 2 /nobreak >nul

echo [2] Starting Frontend on port %FRONTEND_PORT%...
start "Frontend - Port %FRONTEND_PORT%" cmd /k "cd frontend && npm run dev -- --host 127.0.0.1 --port %FRONTEND_PORT%"

echo.
echo ============================================================
echo Services Started
echo ============================================================
echo Django:   http://127.0.0.1:8001
echo Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo.
pause
