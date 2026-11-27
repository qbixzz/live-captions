@echo off
rem Rehearsal: plays an audio or video file and captions it, as if it came from the call.
rem Drag a file onto this .bat, or run:  rehearse.bat <file> [start seconds]
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: rehearse.bat ^<audio or video file^> [start seconds]
  echo Or drag an audio or video file onto rehearse.bat.
  pause
  exit /b 1
)
set "S=%~2"
if "%S%"=="" set "S=0"
call "%~dp0scripts\find_python.bat" || (pause & exit /b 1)
"%PY%" -X utf8 -m live_captions --sim "%~f1" --start %S%
pause
