@echo off
cd /d "%~dp0"
set "PY=C:\Users\Fasder\.workbuddy-ai\binaries\python\envs\bike_sched\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" run.py
pause
