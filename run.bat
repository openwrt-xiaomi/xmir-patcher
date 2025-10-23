@echo off
chcp 65001 >NUL
SET PYTHONUNBUFFERED=TRUE

if "%~1"=="" goto menu

python\python.exe %*
goto :EOF

:menu
python\python.exe menu.py
goto :EOF
