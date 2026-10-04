@echo off
REM startet Lopic im Projekt-venv, ohne Konsolenfenster
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYTHON%" set "PYTHON=pythonw.exe"

REM Hermes-Venv im PATH darf die falschen Pakete liefern
set "PYTHONPATH="

start "" "%PYTHON%" -m lopic
endlocal