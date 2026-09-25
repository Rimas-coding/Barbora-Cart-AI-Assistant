@echo off
chcp 65001 > nul
echo Paleidžiamas Barbora Pirkinių Krepšelio AI Asistentas...
cd /d "%~dp0"
python run.py
pause
