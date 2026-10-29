param([string]$Msi = "$PSScriptRoot\output\Lume-Windows-x64.msi", [string]$Output = "$PSScriptRoot\output\Lume-Setup.exe")
$ErrorActionPreference = 'Stop'
$compiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $compiler)) { throw 'Compilador .NET Framework não encontrado.' }
$msiPath = (Resolve-Path -LiteralPath $Msi).Path
$hash = (Get-FileHash -LiteralPath $msiPath -Algorithm SHA256).Hash
$version = (& py -3.11 -c 'from version import VERSION; print(VERSION)').Trim()
$generated = Join-Path $PSScriptRoot 'build\SetupInfo.cs'
New-Item -ItemType Directory -Force (Split-Path $generated), (Split-Path $Output) | Out-Null
Set-Content -LiteralPath $generated -Encoding UTF8 -Value "using System.Reflection; [assembly: AssemblyTitle(`"Lume Setup`")] [assembly: AssemblyVersion(`"$version.0`")] internal static class SetupInfo { internal const string Hash = `"$hash`"; }"
& $compiler /nologo /target:winexe /platform:anycpu /optimize+ /codepage:65001 /reference:System.Windows.Forms.dll /reference:System.Drawing.dll "/win32manifest:$PSScriptRoot\installer\setup.manifest" "/win32icon:$PSScriptRoot\assets\transcreve.ico" "/resource:$msiPath,Lume.Payload.msi" "/resource:$PSScriptRoot\assets\transcreve.ico,Lume.Icon.ico" "/out:$Output" "$PSScriptRoot\installer\Setup.cs" $generated
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível gerar o Setup.exe.' }
$test = Start-Process -FilePath $Output -ArgumentList '--verify' -Wait -PassThru -WindowStyle Hidden
if ($test.ExitCode -ne 0) { throw 'O MSI incorporado não passou na verificação SHA256.' }
Write-Output "Instalador EXE validado: $Output"
