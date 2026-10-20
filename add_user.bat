@echo off
chcp 65001 > nul
title إضافة متدرب جديد - VJudge Tracker
cd /d "%~dp0"
echo ===================================================
echo             إضافة متدرب جديد إلى النظام
echo ===================================================
echo.
python manage_users.py add
echo.
pause

