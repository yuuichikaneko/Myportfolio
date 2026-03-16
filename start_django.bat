@echo off
cd /d %~dp0\django
set PYTHON_EXE=%~dp0\.venv\Scripts\python.exe
if exist "%PYTHON_EXE%" (
	"%PYTHON_EXE%" manage.py runserver 8001
) else (
	py manage.py runserver 8001
)
