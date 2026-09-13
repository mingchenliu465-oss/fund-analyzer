@echo off
setlocal
echo 正在停止基金分析助手...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":3000 LISTENING"') do taskkill /PID %%P /T /F >nul 2>nul
for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":8000 LISTENING"') do taskkill /PID %%P /T /F >nul 2>nul
echo 已停止。 
pause
endlocal
