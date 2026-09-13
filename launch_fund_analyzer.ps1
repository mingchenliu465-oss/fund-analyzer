$ErrorActionPreference = 'Stop'
$AppRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendRoot = Join-Path $AppRoot 'backend'
$FrontendRoot = Join-Path $AppRoot 'frontend'
$Python = Join-Path $AppRoot '.venv\Scripts\python.exe'
$LogRoot = Join-Path $AppRoot '.launcher-logs'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
function Test-Port([int]$Port) {
    try { $c = [Net.Sockets.TcpClient]::new(); $t = $c.ConnectAsync('127.0.0.1',$Port); $ok=$t.Wait(300); $connected=$c.Connected; $c.Close(); return $ok -and $connected } catch { return $false }
}
if (-not (Test-Port 8000)) {
    if (-not (Test-Path $Python)) { throw "Python environment not found: $Python" }
    Start-Process $Python -ArgumentList '-m','uvicorn','main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory $BackendRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogRoot 'backend.out.log') -RedirectStandardError (Join-Path $LogRoot 'backend.err.log') | Out-Null
}
if (-not (Test-Port 3000)) {
    $Npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $Npm) { throw 'npm.cmd not found. Install Node.js first.' }
    Start-Process $Npm.Source -ArgumentList 'run','dev' -WorkingDirectory $FrontendRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $LogRoot 'frontend.out.log') -RedirectStandardError (Join-Path $LogRoot 'frontend.err.log') | Out-Null
}
$deadline = (Get-Date).AddSeconds(45)
do { Start-Sleep -Milliseconds 500; if (Test-Port 3000) { Start-Process 'http://localhost:3000'; exit 0 } } while ((Get-Date) -lt $deadline)
Start-Process 'http://localhost:3000'
