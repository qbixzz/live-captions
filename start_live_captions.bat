@echo off
rem Live captions of the speaker output (Zoom, Teams, ...). Extra options are passed on, e.g. --whisper small.en. See README.md
cd /d "%~dp0"
call "%~dp0scripts\find_python.bat" || (pause & exit /b 1)
"%PY%" -X utf8 -m live_captions %*
pause
