@echo off
setlocal
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" goto launch
py -3 -c "import sys, tkinter; assert sys.version_info >= (3,11)" >nul 2>&1
if errorlevel 1 goto missing
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -e ".[pdf]"
if errorlevel 1 goto failed
:launch
.venv\Scripts\python.exe -c "import pypdf" >nul 2>&1
if errorlevel 1 .venv\Scripts\python.exe -m pip install -e ".[pdf]"
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m smt2 gui prep
if errorlevel 1 goto failed
exit /b 0
:missing
echo Python 3.11+ with Tkinter and the Python launcher is required.
echo Install Python from https://www.python.org/downloads/windows/ then run again.
pause
exit /b 1
:failed
echo Setup or application failed. Review the error above.
pause
exit /b 1
