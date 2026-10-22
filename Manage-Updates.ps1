param([ValidateSet('Check','Install','Rollback')][string]$Action='Check')
$ErrorActionPreference='Stop'
$configuration=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'sandbox-install.json') -Raw | ConvertFrom-Json
$mode=@{Check='check';Install='update';Rollback='rollback'}[$Action]
& $configuration.python -B (Join-Path $PSScriptRoot 'client_bootstrap.py') $mode
if($LASTEXITCODE -ne 0){throw 'Action stopped. See the installation logs.'}
