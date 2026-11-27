@echo off
rem Downloads Whisper large-v3 and NLLB-200 600M into models\ (about 5.5 GB). Options are passed on, e.g. --whisper small.en
cd /d "%~dp0"
call "%~dp0scripts\find_python.bat" || (pause & exit /b 1)
"%PY%" -X utf8 -m live_captions.download %*
pause
