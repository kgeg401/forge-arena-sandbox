$ErrorActionPreference = 'Stop'
$researchRoot = 'D:\GAMES\CodexAssets\ForgeArenaSandbox'
$manifest = Get-Content -LiteralPath (Join-Path $researchRoot 'research\build-identity.json') -Raw | ConvertFrom-Json
foreach ($entry in $manifest.files) {
    $actual = (Get-FileHash -LiteralPath $entry.path -Algorithm SHA256).Hash
    if ($actual -ne $entry.sha256) { throw "Arena assembly changed: $($entry.path). Review and update evidence before running this probe." }
}
& 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $PSScriptRoot 'ParserProbe\ParserProbe.csproj') --no-restore --nologo -v quiet
if ($LASTEXITCODE -ne 0) { throw 'Parser probe build failed.' }
& 'C:\Program Files\dotnet\dotnet.exe' (Join-Path $researchRoot 'build\ParserProbe\bin\Debug\net8.0\ParserProbe.dll') 'D:\GAMES\MTGA\MTGA_Data\Managed' (Join-Path $researchRoot 'fixtures\empty-board-and-life-diff.json') (Join-Path $researchRoot 'research\parser-probe-result.json')
if ($LASTEXITCODE -ne 0) { throw 'Parser probe failed.' }
