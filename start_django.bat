@echo off
cd /d %~dp0\django
py manage.py runserver 8001
