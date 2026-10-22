$ErrorActionPreference='Stop'
$desktop=[Environment]::GetFolderPath('Desktop')
$shell=New-Object -ComObject WScript.Shell
foreach($mode in @('Mechanics','Brawl')) {
    $path=Join-Path $desktop ('Forge Emry '+$mode+' Test.lnk')
    if(Test-Path -LiteralPath $path){Write-Output "Preserved existing shortcut: $path";continue}
    $shortcut=$shell.CreateShortcut($path)
    $shortcut.TargetPath=Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $shortcut.Arguments='-NoProfile -STA -WindowStyle Hidden -File "'+(Join-Path $PSScriptRoot 'Open-Emry.ps1')+'" -RandomSeed 113'+$(if($mode -eq 'Brawl'){' -Brawl'}else{''})
    $shortcut.WorkingDirectory=$PSScriptRoot
    $shortcut.Description=if($mode -eq 'Brawl'){'100-card,25-life Emry commander foundation; deliberately land-heavy test deck.'}else{'Repeatable60-card Emry mechanics sample against vanilla Forge AI; unrestricted practice copies,20life.'}
    $shortcut.IconLocation='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\MTGA.exe,0'
    $shortcut.Save()
    Write-Output $path
}
