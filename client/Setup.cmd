@echo off
if not exist "%~dp0Setup.exe" (
  echo Extract the complete Windows release ZIP first. Setup.exe is required.
  pause
  exit /b 1
)
start "" /wait "%~dp0Setup.exe"
if errorlevel 1 pause
