$ErrorActionPreference = 'Stop'
$labRoot = 'D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab'
$labExe = Join-Path $labRoot 'MTGA.exe'
foreach ($candidate in @(Get-Process -Name MTGA -ErrorAction SilentlyContinue)) {
    if ($candidate.Path -eq $labExe) {
        Stop-Process -Id $candidate.Id
        Wait-Process -Id $candidate.Id -Timeout 15 -ErrorAction SilentlyContinue
        $candidate.WaitForExit()
    }
    else { throw 'A normal Arena process is open. The lab will not attach to it.' }
}
$archive = Join-Path $labRoot ('attempts\' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $archive -Force | Out-Null
foreach ($name in @('unity-lab.log','native-host-status.json','launch-receipt.json')) {
    $source = Join-Path $labRoot $name
    if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination $archive }
}
Copy-Item -LiteralPath 'D:\GAMES\CodexAssets\ForgeArenaSandbox\build\PreferencePatcher\bin\Debug\netstandard2.1\PreferencePatcher.dll' -Destination (Join-Path $labRoot 'BepInEx\patchers')
Copy-Item -LiteralPath 'D:\GAMES\CodexAssets\ForgeArenaSandbox\build\LabPreferences\bin\Debug\netstandard2.1\LabPreferences.dll' -Destination (Join-Path $labRoot 'BepInEx\core')
Copy-Item -LiteralPath 'D:\GAMES\CodexAssets\ForgeArenaSandbox\build\NativeHost\bin\Debug\netstandard2.1\NativeHost.dll' -Destination (Join-Path $labRoot 'BepInEx\plugins\ForgeArenaSandbox')
& 'C:\Program Files\dotnet\dotnet.exe' 'D:\GAMES\CodexAssets\ForgeArenaSandbox\build\LabLauncher\bin\Debug\net8.0-windows\LabLauncher.dll' $labRoot
if ($LASTEXITCODE -ne 0) { throw 'Isolated lab launch failed.' }
