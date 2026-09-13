@echo off
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":3000 LISTENING"') do taskkill /PID %%P /T /F >nul 2>nul
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 LISTENING"') do taskkill /PID %%P /T /F >nul 2>nul
echo Fund Analyzer stopped.
pause
