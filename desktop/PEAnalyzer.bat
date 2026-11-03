@echo off
setlocal
where wsl.exe >nul 2>&1
if errorlevel 1 (
  echo Windows Subsystem for Linux is required.
  pause
  exit /b 1
)
wsl.exe -d Ubuntu-24.04 -- docker info >nul 2>&1
if not errorlevel 1 goto ready
if not exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
  echo Docker Desktop was not found. Install it and enable Ubuntu-24.04 integration.
  pause
  exit /b 1
)
start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set /a attempts=0
:waitdocker
wsl.exe -d Ubuntu-24.04 -- docker info >nul 2>&1
if not errorlevel 1 goto ready
set /a attempts+=1
if %attempts% GEQ 90 (
  echo Docker did not become ready. Check Docker Desktop WSL integration.
  pause
  exit /b 1
)
timeout /t 2 /nobreak >nul
goto waitdocker
:ready
wsl.exe -d Ubuntu-24.04 -- bash -lc "exec ~/peanalyzer-current/run-oneclick.sh"
if errorlevel 1 (
  echo PEAnalyzer startup failed. See the error above.
  pause
  exit /b 1
)
