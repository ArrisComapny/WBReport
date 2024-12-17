@echo off
chcp 1251
cd /d "%~dp0"
call venv\Scripts\activate
python main.py
pause
