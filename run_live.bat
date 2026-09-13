@echo off
call "%~dp0run_simroad.bat" --web %*
exit /b %ERRORLEVEL%
