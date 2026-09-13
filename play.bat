@echo off
REM Stormhold launcher for Windows.
cd /d "%~dp0"

python -c "import pygame" 2>nul
if errorlevel 1 (
  echo Installing pygame ^(one time only^)...
  python -m pip install --user pygame-ce
)

python -m stormhold %*
if errorlevel 1 pause
