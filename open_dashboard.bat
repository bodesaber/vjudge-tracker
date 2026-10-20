@echo off
cd /d "%~dp0"
start "" /b pythonw server.py 2>nul
start "" "http://127.0.0.1:8765"
