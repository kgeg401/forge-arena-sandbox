$ErrorActionPreference='Stop'
$labRoot='D:\GAMES\CodexAssets\ForgeArenaSandbox\native-lab'
$manifest=Get-Content -LiteralPath 'D:\GAMES\CodexAssets\ForgeArenaSandbox\research\build-identity.json' -Raw | ConvertFrom-Json
function Get-SandboxSha256([string]$Path) {
    # Avoid the Windows PowerShell module auto-loading dependency in hidden launches.
    $stream=[System.IO.File]::OpenRead($Path)
    $algorithm=[System.Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $algorithm.Dispose();$stream.Dispose() }
}
foreach($entry in $manifest.files) {
    if((Get-SandboxSha256 $entry.path) -ne $entry.sha256){throw "Installed assembly changed: $($entry.path)"}
    $labAssembly=Join-Path $labRoot ('MTGA_Data\Managed\'+[System.IO.Path]::GetFileName($entry.path))
    if((Get-SandboxSha256 $labAssembly) -ne $entry.sha256){throw "Lab assembly changed: $labAssembly"}
}
