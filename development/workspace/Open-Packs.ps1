param([switch]$Build)
$ErrorActionPreference='Stop'
$packLab='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab'
& (Join-Path $PSScriptRoot 'Assert-GameIdentity.ps1')
python (Join-Path $PSScriptRoot 'PackBackend\build_pack_catalog.py')
if($LASTEXITCODE -ne 0){throw 'Local pack catalog verification failed'}
if($Build){
    & 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $PSScriptRoot 'NativeHost\NativeHost.csproj') --no-restore
    if($LASTEXITCODE -ne 0){throw 'Native pack host build failed'}
}
foreach($requestName in @('prepare-local-assets.request','start-packs.request','pack-action.request.json','start-decks.request','deck-action.request.json','start-board.request')){
    $requestPath=Join-Path $packLab $requestName
    if(Test-Path -LiteralPath $requestPath){Remove-Item -LiteralPath $requestPath}
}
& (Join-Path $PSScriptRoot 'Deploy-NativeLab.ps1')
$packReceipt=Get-Content (Join-Path $packLab 'launch-receipt.json') -Raw | ConvertFrom-Json
function Wait-PackState([scriptblock]$Condition,[int]$Seconds){
    $packLimit=(Get-Date).AddSeconds($Seconds)
    while((Get-Date) -lt $packLimit){
        if(!(Get-Process -Id $packReceipt.pid -ErrorAction SilentlyContinue)){throw 'The isolated native client exited; inspect unity-lab.log'}
        try{$packState=Get-Content (Join-Path $packLab 'native-host-status.json') -Raw | ConvertFrom-Json}catch{Start-Sleep -Milliseconds 500;continue}
        if([DateTimeOffset]::Parse($packState.utc) -gt [DateTimeOffset]::Parse($packReceipt.utc)){
            if($packState.gap){throw $packState.gap}
            if(& $Condition $packState){return $packState}
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'Timed out waiting for native pack screen readiness'
}
$null=Wait-PackState {param($s) $s.papa} 30
Set-Content (Join-Path $packLab 'prepare-local-assets.request') 'load owned local assets'
$null=Wait-PackState {param($s) $s.phase -eq 'local-assets-ready-render-unverified'} 45
Set-Content (Join-Path $packLab 'start-packs.request') 'open original native pack screen with local profile'
$null=Wait-PackState {param($s) $s.phase -eq 'native-pack-chamber-probe'} 40
$packReadyLimit=(Get-Date).AddSeconds(35)
do {
    Start-Sleep -Milliseconds 500
    $packUiState=$null
    try{$packUiState=Get-Content (Join-Path $packLab 'pack-host-status.json') -Raw | ConvertFrom-Json}catch{}
    $packHost=Get-Content (Join-Path $packLab 'native-host-status.json') -Raw | ConvertFrom-Json
    if($packHost.gap){throw $packHost.gap}
} until(($packUiState.ready -and $packUiState.nativeViews -gt 0 -and [DateTimeOffset]::Parse($packUiState.utc) -gt [DateTimeOffset]::Parse($packReceipt.utc)) -or (Get-Date) -gt $packReadyLimit)
if(!$packUiState.ready -or !$packUiState.nativeViews){throw 'Original pack carousel did not become ready; inspect pack-host-status.json and unity-lab.log'}
Get-Content (Join-Path $packLab 'launch-receipt.json') -Raw
