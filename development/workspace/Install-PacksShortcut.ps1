$ErrorActionPreference='Stop'
$shortcutPath=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Forge Arena Packs.lnk'
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments='-NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $PSScriptRoot 'Open-Packs.ps1')+'"'
$shortcut.WorkingDirectory=$PSScriptRoot
$shortcut.Description='Open original Arena packs using persistent local sandbox balances and collection.'
$shortcut.IconLocation='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\MTGA.exe,0'
$shortcut.Save()
Write-Output $shortcutPath
