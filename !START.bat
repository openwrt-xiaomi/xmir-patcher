@echo off
chcp 65001 >NUL
SET PYTHONUNBUFFERED=TRUE
start cmd /c "cd /d "%~dp0" && python\python.exe menu.py && pause"
