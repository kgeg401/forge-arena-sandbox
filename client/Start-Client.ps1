param([ValidateSet('client','practice','hares','decks')][string]$Mode='client')
$ErrorActionPreference='Stop'
$installRoot=$PSScriptRoot
$configuration=Get-Content -LiteralPath (Join-Path $installRoot 'sandbox-install.json') -Raw | ConvertFrom-Json
$active=Get-Content -LiteralPath (Join-Path $installRoot 'active-version.json') -Raw | ConvertFrom-Json
if($active.version -notmatch '^\d+\.\d+\.\d+(-[A-Za-z0-9.-]+)?$'){throw 'Invalid active sandbox version'}
& $configuration.python -B (Join-Path $installRoot 'client_bootstrap.py') $Mode
if($LASTEXITCODE -ne 0){throw 'The sandbox did not start. Read the error above and the private logs.'}
