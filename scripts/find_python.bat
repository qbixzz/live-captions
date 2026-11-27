@echo off
rem Sets PY to the Python to run, in this order:
rem   1. LIVE_CAPTIONS_PYTHON, which local.bat in the repo folder can set (local.bat is not in git), e.g.
rem        set "LIVE_CAPTIONS_PYTHON=C:\path\to\venv\Scripts\python.exe"
rem   2. .venv\Scripts\python.exe in the repo folder (made by "uv sync")
rem   3. python on PATH
if exist "%~dp0..\local.bat" call "%~dp0..\local.bat"
if defined LIVE_CAPTIONS_PYTHON (
  set "PY=%LIVE_CAPTIONS_PYTHON%"
) else if exist "%~dp0..\.venv\Scripts\python.exe" (
  set "PY=%~dp0..\.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
"%PY%" -c "import faster_whisper, transformers, pyaudiowpatch" 2>nul
if errorlevel 1 (
  echo The Python at "%PY%" cannot load the packages live captions needs.
  echo Double-click setup.bat first. To use a Python you already have, see README.md, Install.
  exit /b 1
)
exit /b 0
