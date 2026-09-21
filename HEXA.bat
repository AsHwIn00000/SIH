@echo off
REM HEXA Desktop Launcher — double-click to start
REM No terminal window shown when using HEXA.vbs

cd /d "%~dp0"
start "" pythonw hexa_launcher.py
