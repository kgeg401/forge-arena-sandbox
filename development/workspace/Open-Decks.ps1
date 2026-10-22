param([switch]$Build)
$ErrorActionPreference='Stop'
$deckLab='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab'
& (Join-Path $PSScriptRoot 'Assert-GameIdentity.ps1')
python (Join-Path $PSScriptRoot 'DeckBackend\build_deck_catalog.py')
if($LASTEXITCODE -ne 0){throw 'Local deck catalog verification failed'}
if($Build){
    & 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $PSScriptRoot 'NativeHost\NativeHost.csproj') --no-restore
    if($LASTEXITCODE -ne 0){throw 'Native deck host build failed'}
}
$seedDirectory=Join-Path $deckLab 'local-deck-seeds'
New-Item -ItemType Directory -Path $seedDirectory -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'decks') -Filter '*.txt' | ForEach-Object {Copy-Item -LiteralPath $_.FullName -Destination $seedDirectory}
foreach($requestName in @('prepare-local-assets.request','start-packs.request','pack-action.request.json','start-board.request','start-decks.request','deck-action.request.json')){
    $requestPath=Join-Path $deckLab $requestName
    if(Test-Path -LiteralPath $requestPath){Remove-Item -LiteralPath $requestPath}
}
& (Join-Path $PSScriptRoot 'Deploy-NativeLab.ps1')
$deckReceipt=Get-Content (Join-Path $deckLab 'launch-receipt.json') -Raw | ConvertFrom-Json
function Wait-DeckState([scriptblock]$Condition,[int]$Seconds){
    $deckLimit=(Get-Date).AddSeconds($Seconds)
    while((Get-Date) -lt $deckLimit){
        if(!(Get-Process -Id $deckReceipt.pid -ErrorAction SilentlyContinue)){throw 'The isolated native client exited; inspect unity-lab.log'}
        try{$deckState=Get-Content (Join-Path $deckLab 'native-host-status.json') -Raw | ConvertFrom-Json}catch{Start-Sleep -Milliseconds 500;continue}
        if([DateTimeOffset]::Parse($deckState.utc) -gt [DateTimeOffset]::Parse($deckReceipt.utc)){
            if($deckState.gap){throw $deckState.gap}
            if(& $Condition $deckState){return $deckState}
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'Timed out waiting for native deck screen readiness'
}
$null=Wait-DeckState {param($s) $s.papa} 30
Set-Content (Join-Path $deckLab 'prepare-local-assets.request') 'load owned local assets'
$null=Wait-DeckState {param($s) $s.phase -eq 'local-assets-ready-render-unverified'} 45
Set-Content (Join-Path $deckLab 'start-decks.request') 'open original native deck editor with local library'
$null=Wait-DeckState {param($s) $s.phase -eq 'native-local-deck-editor'} 40
Get-Content (Join-Path $deckLab 'deck-host-status.json') -Raw
