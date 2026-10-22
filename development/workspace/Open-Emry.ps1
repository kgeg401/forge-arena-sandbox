param([switch]$Brawl,[string]$DeckPath,[string]$OpponentDeckPath,[Nullable[long]]$RandomSeed,[switch]$Build)
$ErrorActionPreference='Stop'
if(-not $DeckPath){$DeckPath=Join-Path $PSScriptRoot $(if($Brawl){'decks\Brawl-Emry-Foundation.txt'}else{'decks\Emry-Mechanics-Practice.txt'})}
if(-not $OpponentDeckPath){$OpponentDeckPath=Join-Path $PSScriptRoot $(if($Brawl){'decks\Brawl-Isamaru-Foundation.txt'}else{'decks\Emry-Mechanics-Opponent.txt'})}
$options=@{Format=$(if($Brawl){'arena-brawl'}else{'practice'});DeckPath=$DeckPath;OpponentDeckPath=$OpponentDeckPath}
if($null -ne $RandomSeed){$options.RandomSeed=$RandomSeed}
if($Build){$options.Build=$true}
$logRoot='D:\GAMES\CodexAssets\ForgeArenaSandbox\launch-logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$logPath=Join-Path $logRoot ('emry-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'.log')
try { & (Join-Path $PSScriptRoot 'Start-Sandbox.ps1') @options *> $logPath }
catch {
    $_ | Out-String | Add-Content -LiteralPath $logPath
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("The Emry test could not start.`n`n$($_.Exception.Message)`n`nDetails: $logPath",'Forge Emry Test') | Out-Null
    exit 1
}
