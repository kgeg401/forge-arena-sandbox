@echo off
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -B "%~dp0setup_client.py"
  if errorlevel 1 pause
) else (
  echo Install Python 3.12 for Windows from https://www.python.org/downloads/windows/
  echo Include Tcl/Tk and the Python launcher in setup. Then run this file again.
  pause
)
