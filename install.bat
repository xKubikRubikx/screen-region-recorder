@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo [1/9] Preparing app folder...
set "SRC_DIR=%~dp0"
if "%SRC_DIR:~-1%"=="\" set "SRC_DIR=%SRC_DIR:~0,-1%"
set "APP_DIR=%LOCALAPPDATA%\ScreenRegionRecorder"
if not exist "%APP_DIR%" mkdir "%APP_DIR%"

for %%F in (region_recorder.py select_region.py post_save_dialog.py recording_overlay.py requirements.txt) do (
  if not exist "%SRC_DIR%\%%F" (
    echo ERROR: %%F was not found next to install.bat
    pause
    exit /b 1
  )
)

echo [2/9] Stopping old recorder processes...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; Get-CimInstance Win32_Process | Where-Object { ($_.Name -in @('pythonw.exe','python.exe','ffmpeg.exe')) -and ($_.CommandLine -like '*ScreenRegionRecorder*' -or $_.CommandLine -like '*region_recorder.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
timeout /t 2 /nobreak >nul

echo [3/9] Copying files...
copy /Y "%SRC_DIR%\region_recorder.py" "%APP_DIR%\region_recorder.py" >nul
copy /Y "%SRC_DIR%\select_region.py" "%APP_DIR%\select_region.py" >nul
copy /Y "%SRC_DIR%\post_save_dialog.py" "%APP_DIR%\post_save_dialog.py" >nul
copy /Y "%SRC_DIR%\recording_overlay.py" "%APP_DIR%\recording_overlay.py" >nul
copy /Y "%SRC_DIR%\requirements.txt" "%APP_DIR%\requirements.txt" >nul

where py >nul 2>&1
if errorlevel 1 (
  echo [4/9] Python not found. Trying to install via winget...
  where winget >nul 2>&1
  if errorlevel 1 (
    echo ERROR: winget is not available. Install Python 3.11+ manually, then run install.bat again.
    pause
    exit /b 1
  )
  winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
)

where py >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python installation failed. Install Python manually and rerun install.bat.
  pause
  exit /b 1
)

echo [5/9] Creating/updating venv...
set "VENV_DIR=%APP_DIR%\.venv"
if not exist "%VENV_DIR%\Scripts\python.exe" (
  py -3 -m venv "%VENV_DIR%" >nul 2>&1
)
if not exist "%VENV_DIR%\Scripts\python.exe" (
  set "VENV_DIR=%APP_DIR%\.venv_alt"
  if exist "%VENV_DIR%" rmdir /S /Q "%VENV_DIR%" >nul 2>&1
  py -3 -m venv "%VENV_DIR%" >nul 2>&1
)
if not exist "%VENV_DIR%\Scripts\python.exe" (
  echo ERROR: Failed to create virtual environment in both .venv and .venv_alt.
  pause
  exit /b 1
)

echo [6/9] Installing Python requirements...
"%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV_DIR%\Scripts\python.exe" -m pip install -r "%APP_DIR%\requirements.txt"

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [7/9] ffmpeg not found. Trying to install via winget...
  where winget >nul 2>&1
  if errorlevel 1 (
    echo ERROR: winget is not available. Install ffmpeg manually, then run install.bat again.
    pause
    exit /b 1
  )
  winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
)

where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo WARNING: ffmpeg may be installed but PATH is not refreshed in this session.
  echo Re-run install.bat after sign out/sign in.
)

echo [8/9] Configuring autorun...
set "RUN_CMD=\"%VENV_DIR%\Scripts\pythonw.exe\" \"%APP_DIR%\region_recorder.py\""
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ScreenRegionRecorder /t REG_SZ /d "%RUN_CMD%" /f >nul

echo [9/9] Starting recorder in background...
start "" "%VENV_DIR%\Scripts\pythonw.exe" "%APP_DIR%\region_recorder.py"

echo.
echo Done.
echo Installed to: %APP_DIR%
echo Hotkeys:
echo   Ctrl+X       - cycle: region - start - stop
echo   Ctrl+Shift+R - force reselect region
echo   Ctrl+Shift+Q - exit app
pause
endlocal
