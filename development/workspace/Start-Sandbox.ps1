param([switch]$Build,[switch]$FullControl,[ValidateSet('starter','attack-open','attack-multi','attack-blocked','defend','duel','mixed-duel','opening-duel','spell-duel','trigger-duel','blue-duel','custom-duel','brawl-duel','counter-ready','counter-ready-white','counter-ready-idle','blue-bounce','blue-wrong-color','trigger-orator','trigger-orator-double','hare-chain','defend-arrow','lethal-win','defend-lethal','discard','vanilla-costs','defend-ox','attack-swift','attack-double-blocked','draw-ready','draw-wrong-color')][string]$Scenario='duel',[Nullable[long]]$RandomSeed,[string]$DeckPath,[string]$OpponentDeckPath,[ValidateSet('practice','arena-brawl')][string]$Format='practice')
$ErrorActionPreference='Stop'
$privateRoot='D:\GAMES\CodexAssets\ForgeArenaSandbox'
$labRoot=Join-Path $privateRoot 'native-lab'
$labExe=Join-Path $labRoot 'MTGA.exe'
$importedDecks=$null
if($DeckPath) {
    $deckArgs=@((Join-Path $PSScriptRoot 'ForgeBackend\deck_import.py'),$DeckPath)
    $deckArgs+=@('--format',$Format)
    if($OpponentDeckPath){$deckArgs+=@('--opponent',$OpponentDeckPath)}
    $deckOutput=& python @deckArgs 2>&1
    if($LASTEXITCODE -ne 0){throw ($deckOutput -join "`n")}
    $importedDecks=($deckOutput -join "`n") | ConvertFrom-Json
    $Scenario=if($Format -eq 'arena-brawl'){'brawl-duel'}else{'custom-duel'}
} elseif($OpponentDeckPath -or $Scenario -eq 'custom-duel' -or $Scenario -eq 'brawl-duel' -or $Format -eq 'arena-brawl'){throw 'Select a local deck file before starting a custom match.'}
& (Join-Path $PSScriptRoot 'Assert-GameIdentity.ps1')
python (Join-Path $PSScriptRoot 'ForgeBackend\build_card_coverage.py')
if($LASTEXITCODE -ne 0){throw 'Owned Arena/Forge card mapping verification failed'}
foreach($candidate in @(Get-Process -Name MTGA -ErrorAction SilentlyContinue)) {
    if($candidate.Path -ne $labExe){throw 'Normal Arena is open; close it before starting the isolated sandbox.'}
}
if($Build) {
    python (Join-Path $PSScriptRoot 'ForgeBackend\prepare_backend.py')
    if($LASTEXITCODE -ne 0){throw 'Forge backend build failed'}
    & 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $PSScriptRoot 'NativeHost\NativeHost.csproj') --no-restore
    if($LASTEXITCODE -ne 0){throw 'Native host build failed'}
}
$controlFlag=Join-Path $labRoot 'full-control-test.flag'
if($FullControl){Set-Content -LiteralPath $controlFlag -Value 'diagnostic: hold every priority window'}
elseif(Test-Path -LiteralPath $controlFlag){Remove-Item -LiteralPath $controlFlag}
foreach($candidate in @(Get-Process -Name MTGA -ErrorAction SilentlyContinue)) {
    if($candidate.Path -ne $labExe){throw 'Normal Arena opened during preparation; close it before starting the isolated sandbox.'}
    Stop-Process -Id $candidate.Id
    $candidate.WaitForExit()
}
$ipcRoot=Join-Path $labRoot 'forge-ipc'
if(Test-Path -LiteralPath $ipcRoot) {
    if((Resolve-Path -LiteralPath $ipcRoot).Path -ne 'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab\forge-ipc'){throw 'Unexpected IPC archive source'}
    $metadataPath=Join-Path $ipcRoot 'backend-process.json'
    if(Test-Path -LiteralPath $metadataPath) {
        $metadata=Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
        $backend=Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$metadata.pid)" -ErrorAction SilentlyContinue
        if($backend) {
            if($backend.CommandLine -notlike '*ForgeLandEngine*' -or $backend.CommandLine -notlike '*D:\GAMES\CodexAssets\ForgeArenaSandbox*'){throw 'Backend PID no longer matches the private engine'}
            Set-Content -LiteralPath (Join-Path $ipcRoot 'stop.request') -Value 'start fresh sandbox; retain prior evidence'
            Wait-Process -Id $metadata.pid -Timeout 15 -ErrorAction SilentlyContinue
            if(Get-Process -Id $metadata.pid -ErrorAction SilentlyContinue){throw 'Prior backend did not stop'}
        }
    }
    $destination=Join-Path $labRoot ('forge-ipc-evidence-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    Move-Item -LiteralPath $ipcRoot -Destination $destination
}
New-Item -ItemType Directory -Path $ipcRoot -Force | Out-Null
$scenarioSettings=@{scenario=$Scenario}
if($importedDecks){$scenarioSettings.localDeck=$importedDecks.localDeck;$scenarioSettings.opponentDeck=$importedDecks.opponentDeck}
if($null -ne $RandomSeed){$scenarioSettings.randomSeed=[long]$RandomSeed}
$scenarioSettings | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ipcRoot 'scenario.json')
python (Join-Path $PSScriptRoot 'ForgeBackend\start_backend.py')
if($LASTEXITCODE -ne 0){throw 'Forge backend did not become ready'}
& (Join-Path $PSScriptRoot 'Open-NativeBoard.ps1') -Redeploy
