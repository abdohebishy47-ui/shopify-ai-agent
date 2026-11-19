@echo off
cd /d "%~dp0"
title El Hoda AI Agent - Server & Tunnel
echo ===================================================
echo     El Hoda Computer HCS - AI Agent System
echo ===================================================
echo.
echo Starting Local AI Server on port 8000...
start /b python run.py
timeout /t 3 /nobreak >nul
echo Starting Permanent Public Tunnel (ngrok)...
start "ngrok Tunnel" "%~dp0ngrok.exe" http 8000
echo.
echo ===================================================
echo  System is LIVE!
echo  Permanent Public URL: https://snipping-spew-tumbling.ngrok-free.dev
echo  Local URL:            http://localhost:8000
echo ===================================================
echo.
pause
