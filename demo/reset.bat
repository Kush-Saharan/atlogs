@echo off
REM Reset + seed the Atlas demo. Works from ANY directory (double-click or run).
REM Paths are resolved relative to this file, so cwd doesn't matter.
REM   Usage:  demo\reset.bat            (connectors only)
REM           demo\reset.bat --reset-only
REM           demo\reset.bat --pdf "C:\path\to\pdfs"
setlocal
set "PY=%~dp0..\backend\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Could not find the backend venv python at:
  echo   %PY%
  echo Make sure the backend venv exists ^(backend\.venv^).
  exit /b 1
)
"%PY%" "%~dp0reset_and_seed.py" %*
