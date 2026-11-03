param(
    [string]$Arena,
    [string]$Profiles = (Join-Path $PSScriptRoot 'arena-builds.json'),
    [string]$Report,
    [switch]$NoDialog
)
$ErrorActionPreference = 'Stop'
if (-not $Arena) {
    Add-Type -AssemblyName System.Windows.Forms
    $picker = New-Object System.Windows.Forms.FolderBrowserDialog
    $picker.Description = 'Select the official Arena folder containing MTGA.exe. In Steam: Manage > Browse local files.'
    if ($picker.ShowDialog() -ne 'OK') { exit 0 }
    $Arena = $picker.SelectedPath
}
$root = [IO.Path]::GetFullPath($Arena)
$profilesData = Get-Content -LiteralPath $Profiles -Raw -Encoding UTF8 | ConvertFrom-Json
$observed = @{}
$comparisons = @()
foreach ($build in $profilesData.builds) {
    $differences = @()
    foreach ($entry in $build.arenaFiles.PSObject.Properties) {
        $relative = $entry.Name
        if (-not $observed.ContainsKey($relative)) {
            $path = Join-Path $root $relative
            $file = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
            $record = [ordered]@{ path = $relative; exists = [bool]($file -and -not $file.PSIsContainer); sha256 = $null; bytes = $null; error = $null }
            if ($record.exists) {
                try {
                    $stream = [IO.File]::OpenRead($path)
                    $hasher = [Security.Cryptography.SHA256]::Create()
                    try { $record.sha256 = [BitConverter]::ToString($hasher.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
                    finally { $stream.Dispose(); $hasher.Dispose() }
                    $record.bytes = $file.Length
                } catch { $record.error = $_.Exception.Message }
            }
            $observed[$relative] = $record
        }
        if ($observed[$relative].sha256 -ne $entry.Value) {
            $differences += [ordered]@{ path = $relative; expected = $entry.Value; actual = $observed[$relative].sha256; exists = $observed[$relative].exists }
        }
    }
    $comparisons += [ordered]@{ build = $build.arenaBuild; matches = ($differences.Count -eq 0); differences = @($differences) }
}
$exe = Get-Item -LiteralPath (Join-Path $root 'MTGA.exe') -ErrorAction SilentlyContinue
$result = [ordered]@{
    schema = 1
    generatedUtc = [DateTime]::UtcNow.ToString('o')
    selectedFolder = $root
    executableFound = [bool]($exe -and -not $exe.PSIsContainer)
    productVersion = $(if ($exe) { $exe.VersionInfo.ProductVersion } else { $null })
    accepted = [bool](@($comparisons | Where-Object { $_.matches }).Count)
    comparisons = @($comparisons)
    files = @($observed.Values | Sort-Object { $_.path })
}
if (-not $Report) { $Report = Join-Path ([Environment]::GetFolderPath('Desktop')) ('Arena-Compatibility-' + [DateTime]::Now.ToString('yyyyMMdd-HHmmss') + '.json') }
$result | ConvertTo-Json -Depth 8 | Out-File -LiteralPath $Report -Encoding UTF8
Write-Output ('Report saved: ' + $Report)
if (-not $NoDialog) {
    Add-Type -AssemblyName System.Windows.Forms
    $message = $(if ($result.accepted) { 'This folder matches a supported Arena build.' } elseif (-not $result.executableFound) { 'MTGA.exe was not found. Select the folder opened by Steam > Manage > Browse local files.' } else { 'This Arena installation differs from the tested builds. Send the report so we can identify the exact files.' })
    [Windows.Forms.MessageBox]::Show(($message + "`n`nReport saved to:`n" + $Report), 'Arena file check') | Out-Null
}
