$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path $desktop '基金分析助手.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $root '启动基金分析助手.bat'
$shortcut.WorkingDirectory = $root
$shortcut.Description = '启动基金分析助手'
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
$shortcut.Save()
Write-Host "已创建桌面图标：$shortcutPath"
