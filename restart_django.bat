@echo off
REM Django development server restart script

echo Stopping existing Django processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq*django*" >nul 2>&1

cd F:\Python\Myportfolio

echo Starting Django development server...
start "Django Server" cmd /k "cd F:\Python\Myportfolio && .\.venv\Scripts\python.exe django\manage.py runserver 8001"

echo Django server restarted on port 8001
echo Waiting 5 seconds...
timeout /t 5 /nobreak

echo Done!
