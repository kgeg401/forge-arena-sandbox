$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$outputBase=if($env:FORGE_ARENA_TEST_OUTPUT){$env:FORGE_ARENA_TEST_OUTPUT}else{Join-Path ([IO.Path]::GetTempPath()) 'ForgeArenaSandbox-checks'}
$output=Join-Path $outputBase ('bootstrap-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $output -Force | Out-Null
$test=Join-Path $output 'BootstrapTests.exe'
& $compiler /nologo /target:exe /platform:x64 /optimize+ /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll /main:BootstrapTests ('/out:'+$test) (Join-Path $PSScriptRoot 'SetupBootstrap.cs') (Join-Path $PSScriptRoot 'SetupBootstrapTests.cs')
if($LASTEXITCODE -ne 0){throw 'Bootstrap test compilation failed'}
& $test
if($LASTEXITCODE -ne 0){throw 'Bootstrap flow checks failed'}
