# Django development server restart script
Write-Host "Stopping existing Django processes..." -ForegroundColor Yellow

# Pythonプロセスの情報を取得
$processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -match "manage.py.*runserver" -or 
    $_.CommandLine -match "django"
}

if ($processes) {
    Write-Host "Found $(($processes | Measure-Object).Count) Django process(es). Stopping..."
    $processes | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped process ID: $($_.Id)"
    }
    Start-Sleep -Seconds 2
}

Write-Host "Starting Django development server..." -ForegroundColor Green
cd F:\Python\Myportfolio

# Start Django server in background
$djangoProcess = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "django\manage.py", "runserver", "8001" `
    -PassThru `
    -NoNewWindow

Write-Host "Django server started with PID: $($djangoProcess.Id)" -ForegroundColor Green
Write-Host "Server is starting on http://127.0.0.1:8001" -ForegroundColor Cyan

Start-Sleep -Seconds 3
Write-Host "Server should now be running. Try accessing the frontend to generate a new configuration." -ForegroundColor Cyan
