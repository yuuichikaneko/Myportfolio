Set-Location "$PSScriptRoot/django"
$python = Join-Path $PSScriptRoot ".venv/Scripts/python.exe"
if (-not (Test-Path $python)) {
	$python = "py"
}

& $python manage.py runserver 8001
