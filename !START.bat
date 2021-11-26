@echo off
chcp 866 >NUL
SET PYTHONUNBUFFERED=TRUE
start cmd /k python\python.exe menu.py
