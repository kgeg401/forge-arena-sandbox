$ErrorActionPreference='Stop'
$shortcutPath=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Forge Arena Custom Decks.lnk'
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments='-NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $PSScriptRoot 'Open-Playable.ps1')+'" -ChooseDecks'
$shortcut.WorkingDirectory=$PSScriptRoot
$shortcut.Description='Choose two supported practice decks, then play in the isolated native Arena client. Cancel leaves the current game open.'
$shortcut.IconLocation='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\MTGA.exe,0'
$shortcut.Save()
Write-Output $shortcutPath
