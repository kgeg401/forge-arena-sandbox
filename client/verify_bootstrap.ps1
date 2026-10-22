$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$output = if ($env:FORGE_ARENA_TEST_OUTPUT) { $env:FORGE_ARENA_TEST_OUTPUT } else { Join-Path $env:TEMP 'forge-arena-source-checks' }
New-Item -ItemType Directory -Path $output -Force | Out-Null
$test = Join-Path $output 'BootstrapTests.exe'
& $compiler /nologo /target:exe /platform:x64 /optimize+ /r:System.Windows.Forms.dll /r:System.Drawing.dll /r:System.Web.Extensions.dll /main:BootstrapTests ('/out:' + $test) (Join-Path $PSScriptRoot 'adapter-source/SetupBootstrap.cs') (Join-Path $PSScriptRoot 'adapter-source/SetupBootstrapTests.cs')
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap check compilation failed' }
& $test
if ($LASTEXITCODE -ne 0) { throw 'Bootstrap flow checks failed' }
