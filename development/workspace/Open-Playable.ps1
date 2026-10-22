param([ValidateSet('duel','mixed-duel','opening-duel','spell-duel','trigger-duel','blue-duel')][string]$Scenario='duel',[string]$DeckPath,[string]$OpponentDeckPath,[switch]$ChooseDecks)
$ErrorActionPreference='Stop'
$logRoot='D:\GAMES\CodexAssets\ForgeArenaSandbox\launch-logs'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$launchLog=Join-Path $logRoot ('play-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff')+'.log')
try {
    if($ChooseDecks){
        Add-Type -AssemblyName PresentationFramework
        $picker=New-Object Microsoft.Win32.OpenFileDialog
        $picker.Filter='Deck text files (*.txt)|*.txt';$picker.InitialDirectory=Join-Path $PSScriptRoot 'decks'
        $savedExports='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\local-deck-exports'
        if((Test-Path -LiteralPath $savedExports) -and @(Get-ChildItem -LiteralPath $savedExports -Filter '*.txt').Count -gt 0){$picker.InitialDirectory=$savedExports}
        $picker.Title='Choose your supported sandbox deck'
        if($picker.ShowDialog() -ne $true){return};$DeckPath=$picker.FileName
        $picker.Title='Choose the opponent sandbox deck'
        if($picker.ShowDialog() -ne $true){return};$OpponentDeckPath=$picker.FileName
    }
    $options=@{Scenario=$Scenario}
    if($DeckPath){$options.DeckPath=$DeckPath};if($OpponentDeckPath){$options.OpponentDeckPath=$OpponentDeckPath}
    & (Join-Path $PSScriptRoot 'Start-Sandbox.ps1') @options *> $launchLog
} catch {
    $_ | Out-String | Add-Content -LiteralPath $launchLog
    Add-Type -AssemblyName PresentationFramework
    [System.Windows.MessageBox]::Show("The local sandbox could not start.`n`n$($_.Exception.Message)`n`nDetails: $launchLog",'Forge Arena Sandbox') | Out-Null
    exit 1
}
