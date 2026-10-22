$ErrorActionPreference='Stop'
$hareShortcutPath=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Forge Arena Hares.lnk'
$hareShell=New-Object -ComObject WScript.Shell
$hareShortcut=$hareShell.CreateShortcut($hareShortcutPath)
$hareShortcut.TargetPath=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$hareShortcut.Arguments='-NoProfile -STA -WindowStyle Hidden -ExecutionPolicy Bypass -File "'+(Join-Path $PSScriptRoot 'Open-Playable.ps1')+'" -DeckPath "'+(Join-Path $PSScriptRoot 'decks\Hare-Apparent-Practice.txt')+'" -OpponentDeckPath "'+(Join-Path $PSScriptRoot 'decks\White-Lifegain.txt')+'"'
$hareShortcut.WorkingDirectory=$PSScriptRoot
$hareShortcut.Description='Start a normally shuffled 60-card Hare Apparent practice match in the isolated Arena sandbox.'
$hareShortcut.IconLocation='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\MTGA.exe,0'
$hareShortcut.Save()
Write-Output $hareShortcutPath
