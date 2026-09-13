$ErrorActionPreference = 'Stop'

$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Join-Path $AppRoot 'backend'
$FrontendRoot = Join-Path $AppRoot 'frontend'
$Python = Join-Path $AppRoot '.venv\Scripts\python.exe'
$LogRoot = Join-Path $AppRoot '.launcher-logs'

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null

function Test-Port([int]$Port) {
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $task = $client.ConnectAsync('127.0.0.1', $Port)
        $ok = $task.Wait(300)
        $client.Close()
        return $ok -and $client.Connected
    } catch { return $false }
}

if (-not (Test-Port 8000)) {
    if (-not (Test-Path $Python)) { throw "未找到 Python 环境：$Python" }
    Start-Process -FilePath $Python -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8000' `
        -WorkingDirectory $BackendRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogRoot 'backend.out.log') `
        -RedirectStandardError (Join-Path $LogRoot 'backend.err.log') | Out-Null
}

if (-not (Test-Port 3000)) {
    $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $Npm) { throw '未找到 npm.cmd，请先安装 Node.js。' }
    Start-Process -FilePath $Npm.Source -ArgumentList 'run','dev' `
        -WorkingDirectory $FrontendRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogRoot 'frontend.out.log') `
        -RedirectStandardError (Join-Path $LogRoot 'frontend.err.log') | Out-Null
}

$deadline = (Get-Date).AddSeconds(45)
do {
    Start-Sleep -Milliseconds 500
    if (Test-Port 3000) { Start-Process 'http://localhost:3000'; exit 0 }
} while ((Get-Date) -lt $deadline)

Start-Process 'http://localhost:3000'
Write-Warning '前端仍在启动中，页面可能需要几秒钟后刷新。'
