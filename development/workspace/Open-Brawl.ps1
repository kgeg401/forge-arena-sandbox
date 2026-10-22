param([string]$DeckPath,[string]$OpponentDeckPath,[switch]$Build)
$ErrorActionPreference='Stop'
if(-not $DeckPath){$DeckPath=Join-Path $PSScriptRoot 'decks\Brawl-Isamaru-Foundation.txt'}
$options=@{Format='arena-brawl';DeckPath=$DeckPath}
if($OpponentDeckPath){$options.OpponentDeckPath=$OpponentDeckPath}
if($Build){$options.Build=$true}
$logRoot='D:\GAMES\CodexAssets\ForgeArenaSandbox\launch-logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$logPath=Join-Path $logRoot ('brawl-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'.log')
try { & (Join-Path $PSScriptRoot 'Start-Sandbox.ps1') @options *> $logPath }
catch {
    $_ | Out-String | Add-Content -LiteralPath $logPath
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("The Brawl test could not start.`n`n$($_.Exception.Message)`n`nDetails: $logPath",'Forge Arena Brawl Test') | Out-Null
    exit 1
}
