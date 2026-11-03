@echo off
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0Check-Arena-Files.ps1"
if errorlevel 1 pause
