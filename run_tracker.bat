@echo off
chcp 65001 > nul
title VJudge Trainees Activity Tracker
cd /d "%~dp0"
echo ===================================================
echo     VJudge Trainees Activity Tracker (تشغيل المراقبة)
echo ===================================================
echo.
python tracker.py --watch
pause

