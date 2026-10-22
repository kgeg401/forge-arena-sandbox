$ErrorActionPreference='Stop'
$path=Join-Path ([Environment]::GetFolderPath('Desktop')) 'Forge Arena Brawl Test.lnk'
if(Test-Path -LiteralPath $path){throw 'The Brawl shortcut already exists; it was preserved.'}
$shell=New-Object -ComObject WScript.Shell
$shortcut=$shell.CreateShortcut($path)
$shortcut.TargetPath=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$shortcut.Arguments='-NoProfile -STA -WindowStyle Hidden -File "'+(Join-Path $PSScriptRoot 'Open-Brawl.ps1')+'"'
$shortcut.WorkingDirectory=$PSScriptRoot
$shortcut.Description='Experimental 100-card Isamaru Brawl rules fixture; use Forge Emry Brawl Test for the separate Emry fixture.'
$shortcut.IconLocation='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\MTGA.exe,0'
$shortcut.Save()
Write-Output $path
