@echo off
setlocal EnableExtensions

set "APP_DIR=%LOCALAPPDATA%\ScreenRegionRecorder"
set "SCRIPT_PATH=%APP_DIR%\region_recorder.py"

echo [1/4] Stopping running recorder processes...
for /f "skip=1 tokens=2 delims=," %%P in ('wmic process where "name='pythonw.exe' and commandline like '%%region_recorder.py%%'" get processid /format:csv 2^>nul') do (
  if not "%%P"=="" taskkill /PID %%P /F >nul 2>&1
)

echo [2/4] Removing autorun registry key...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ScreenRegionRecorder /f >nul 2>&1

echo [3/4] Removing installed files...
if exist "%APP_DIR%" rmdir /S /Q "%APP_DIR%"

echo [4/4] Done.
echo App removed from: %APP_DIR%
pause
endlocal
