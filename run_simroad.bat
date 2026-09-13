@echo off
setlocal
set "ROOT=%~dp0"
if exist "%ROOT%.venv\Scripts\python.exe" (
  "%ROOT%.venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    "%ROOT%.venv\Scripts\python.exe" "%ROOT%scripts\run_all.py" %*
    goto finished
  )
)
if exist "%ROOT%.venv-runner\Scripts\python.exe" (
  "%ROOT%.venv-runner\Scripts\python.exe" "%ROOT%scripts\run_all.py" %*
  goto finished
)
py -3.12 -c "import sys" >nul 2>&1
if not errorlevel 1 (
  py -3.12 "%ROOT%scripts\run_all.py" %*
  goto finished
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 (
  python "%ROOT%scripts\run_all.py" %*
  goto finished
)
echo Python 3.11+ is required ^(3.12 recommended^). Install Python, then rerun this file.
exit /b 1
:finished
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" (
  echo.
  echo Simroad stopped with an error. Read the message above.
  if not defined SIMROAD_NO_PAUSE pause
)
exit /b %RESULT%
