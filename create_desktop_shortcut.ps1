$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Fund Analyzer.lnk'))
$shortcut.TargetPath = Join-Path $root 'launch_fund_analyzer.bat'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Fund Analyzer'
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,13"
$shortcut.Save()
Write-Host 'Desktop shortcut created.'
