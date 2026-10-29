@echo off
REM Pomodmer self-healing launcher.
REM NOTE: kept ASCII-only on purpose - cmd.exe mangles non-ASCII in .bat depending on codepage.
setlocal
cd /d "%~dp0"

where node >nul 2>nul
if errorlevel 1 (
  echo [pomodmer] Node.js not found. Install Node.js 22+ and retry.
  pause
  exit /b 1
)

if not exist "node_modules\cordis" (
  echo [pomodmer] dependencies missing -^> npm install ...
  call npm install
  if errorlevel 1 (
    echo [pomodmer] npm install failed.
    pause
    exit /b 1
  )
)

if "%POMODMER_PORT%"=="" set POMODMER_PORT=5173
echo [pomodmer] starting on http://127.0.0.1:%POMODMER_PORT%/
echo [pomodmer] press Ctrl+C to stop
node src\pom.mjs %*
endlocal
