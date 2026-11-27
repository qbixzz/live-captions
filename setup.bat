@echo off
rem One-time setup: the Python packages (uv sync) and the models. Safe to run again.
cd /d "%~dp0"
echo.
echo   Live captions setup
echo   ===================
echo.
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed. Install it with this command in PowerShell, then run setup.bat again:
  echo.
  echo   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  echo.
  pause
  exit /b 1
)
echo [1/3] Installing the Python packages. The first time this downloads about 5 GB.
uv sync
if errorlevel 1 (
  echo Installing the packages failed. See the messages above.
  pause
  exit /b 1
)
echo.
echo [2/3] Checking the GPU
.venv\Scripts\python -c "import sys, torch; ok = torch.cuda.is_available(); print('      ' + (torch.cuda.get_device_name(0) if ok else 'No CUDA GPU found')); sys.exit(0 if ok else 1)"
if errorlevel 1 echo       Update the NVIDIA driver to version 570 or newer. See README.md, Requirements.
echo.
echo [3/3] Downloading the models into models\, about 5.5 GB. Files already there are skipped.
.venv\Scripts\python -X utf8 -m live_captions.download
if errorlevel 1 (
  echo Downloading the models failed. See the messages above, then run setup.bat again.
  pause
  exit /b 1
)
if not exist terms.txt (
  copy terms.example.txt terms.txt >nul
  echo.
  echo Made terms.txt. Put the names and terms you expect to hear in it, so Whisper spells them right.
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo.
  echo Note: ffmpeg was not found. It is only needed for rehearse.bat. Install it with: winget install Gyan.FFmpeg
)
echo.
echo Done. Double-click start_live_captions.bat to start.
echo.
pause
