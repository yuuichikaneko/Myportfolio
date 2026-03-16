Set-Location "$PSScriptRoot"

function Get-FreePort {
	param(
		[int]$StartPort = 5173,
		[int]$EndPort = 5200
	)

	for ($port = $StartPort; $port -le $EndPort; $port++) {
		$listener = $null
		try {
			$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
			$listener.Start()
			$listener.Stop()
			return $port
		}
		catch {
			if ($listener) {
				$listener.Stop()
			}
		}
	}

	throw "No free port found in range $StartPort-$EndPort"
}

Write-Output "============================================================"
Write-Output "Django + Frontend Startup"
Write-Output "============================================================"
Write-Output ""

$python = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) {
	$python = "py"
}

Write-Output "[1] Starting Django on port 8001..."
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$PSScriptRoot/django'; & '$python' manage.py runserver 8001"

Start-Sleep -Seconds 2

$frontendPort = Get-FreePort
Write-Output "[2] Starting Frontend on port $frontendPort..."
Start-Process powershell -ArgumentList '-NoExit', '-Command', "cd '$PSScriptRoot/frontend'; npm run dev -- --host 127.0.0.1 --port $frontendPort"

Write-Output ""
Write-Output "============================================================"
Write-Output "Services Started"
Write-Output "============================================================"
Write-Output "Django:   http://127.0.0.1:8001"
Write-Output "Frontend: http://127.0.0.1:$frontendPort"
