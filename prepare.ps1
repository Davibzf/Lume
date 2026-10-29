param([string]$FFmpeg = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force vendor/runtime, vendor/downloads, licenses | Out-Null
function Download-Verified([string]$Url, [string]$Path, [string]$Sha256) {
    if (-not (Test-Path -LiteralPath $Path)) { Invoke-WebRequest -Uri $Url -OutFile $Path }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Sha256) {
        throw "SHA256 inválido: $Path. Remova o download incompleto e tente novamente."
    }
}
$archive = 'vendor/downloads/whisper-bin-x64.zip'
Download-Verified 'https://github.com/ggml-org/whisper.cpp/releases/download/v1.9.2/whisper-bin-x64.zip' $archive '49dcc16de826f20bd53d44f947a1ae49dfa81f86cad67a64d80820cb192d674a'
Expand-Archive -LiteralPath $archive -DestinationPath vendor/unpacked -Force
Copy-Item vendor/unpacked/Release/whisper-cli.exe vendor/runtime -Force
Copy-Item vendor/unpacked/Release/ggml*.dll vendor/runtime -Force
Copy-Item vendor/unpacked/Release/whisper.dll vendor/runtime -Force
if (-not (Test-Path vendor/runtime/ggml-cpu-x64.dll)) { throw 'Backend x64 básico ausente.' }
foreach ($name in 'msvcp140.dll','vcruntime140.dll','vcruntime140_1.dll','vcomp140.dll') {
    $dll = Join-Path $env:WINDIR "System32\$name"
    if (-not (Test-Path -LiteralPath $dll)) { throw "Runtime Microsoft ausente: $name. Use o ambiente de compilação descrito em docs/BUILD.md." }
    Copy-Item -LiteralPath $dll -Destination vendor/runtime -Force
}
if ($FFmpeg) {
    if (-not (Test-Path -LiteralPath $FFmpeg)) { throw 'ffmpeg.exe não encontrado.' }
    Copy-Item -LiteralPath $FFmpeg -Destination vendor/runtime/ffmpeg.exe -Force
    $runtimeSource = Split-Path -Parent (Resolve-Path -LiteralPath $FFmpeg).Path
    foreach ($name in 'FFmpeg-LGPL-2.1.txt','FFmpeg-build.txt') {
        $licensePath = Join-Path $runtimeSource $name
        if (-not (Test-Path -LiteralPath $licensePath)) { throw "Arquivo de distribuição ausente: $name" }
        Copy-Item -LiteralPath $licensePath -Destination licenses -Force
    }
} else {
    $lock = Get-Content runtime-lock.json -Raw | ConvertFrom-Json
    foreach ($entry in $lock.files) {
        $download = Join-Path 'vendor/downloads' $entry.name
        Download-Verified $entry.url $download $entry.sha256
        $destination = if ($entry.name -eq 'ffmpeg.exe') { 'vendor/runtime/ffmpeg.exe' } else { Join-Path 'licenses' $entry.name }
        Copy-Item -LiteralPath $download -Destination $destination -Force
    }
}
& vendor/runtime/ffmpeg.exe -version | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { throw 'FFmpeg não executou neste sistema.' }
& vendor/runtime/whisper-cli.exe --help 2>&1 | Select-Object -First 3
if ($LASTEXITCODE -ne 0) { throw 'Whisper não executou neste sistema.' }
Write-Output 'Motor preparado com backends de CPU x64. Nenhum modelo é incorporado.'
