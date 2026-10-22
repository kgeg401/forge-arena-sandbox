param([switch]$Redeploy)
$ErrorActionPreference = 'Stop'
$labRoot = 'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab'
& (Join-Path $PSScriptRoot 'Assert-GameIdentity.ps1')
if ($Redeploy) { & (Join-Path $PSScriptRoot 'Deploy-NativeLab.ps1') }
$receipt = Get-Content -LiteralPath (Join-Path $labRoot 'launch-receipt.json') -Raw | ConvertFrom-Json
$process = Get-Process -Id $receipt.pid -ErrorAction Stop
# MainModule/Path can be temporarily unavailable immediately after ResumeThread.
$pathLimit=(Get-Date).AddSeconds(5)
while([string]::IsNullOrEmpty($process.Path) -and (Get-Date) -lt $pathLimit){
    Start-Sleep -Milliseconds 100
    $process=Get-Process -Id $receipt.pid -ErrorAction Stop
}
if ($process.Path -ne $receipt.executable -or !$receipt.appContainer -or $receipt.capabilityCount -ne 0) { throw 'Invalid lab launch receipt.' }
function Wait-NativeState([scriptblock]$Condition, [int]$Seconds, [string]$Description) {
    $limit = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $limit) {
        if ($process.HasExited) { throw 'Lab process exited.' }
        try { $state = Get-Content -LiteralPath (Join-Path $labRoot 'native-host-status.json') -Raw | ConvertFrom-Json }
        catch { Start-Sleep -Milliseconds 500; continue }
        if ([DateTimeOffset]::Parse($state.utc) -lt [DateTimeOffset]::Parse($receipt.utc)) { Start-Sleep -Milliseconds 500; continue }
        if (& $Condition $state) { return $state }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out: $Description. Read native-host-status.json and unity-lab.log."
}
$state = Wait-NativeState { param($s) $s.papa } 25 'native application context'
if (!$state.realDatabase) {
    Set-Content -LiteralPath (Join-Path $labRoot 'prepare-local-assets.request') -Value 'load cached native assets'
    $state = Wait-NativeState { param($s) $s.phase -eq 'local-assets-ready-render-unverified' } 45 'native local database preparation'
}
if (!$state.nativeGameManager) {
    Set-Content -LiteralPath (Join-Path $labRoot 'start-board.request') -Value 'open isolated native board'
}
$expectedSession=$null
if(Test-Path -LiteralPath (Join-Path $labRoot 'enable-forge-land-test.flag')){$expectedSession=(Get-Content -LiteralPath (Join-Path $labRoot 'forge-ipc\state.json') -Raw | ConvertFrom-Json).session}
$state = Wait-NativeState { param($s) $s.nativeState -ge 1 -and (!$expectedSession -or $s.forge.session -eq $expectedSession) -and $s.scenes -contains 'DuelScene' -and $s.scenes -notcontains 'PreGameScene' } 45 'native board readiness'
$state | ConvertTo-Json -Depth 8
