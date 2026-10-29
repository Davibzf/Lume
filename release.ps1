$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force output | Out-Null
$lock = Get-Content runtime-lock.json -Raw | ConvertFrom-Json
foreach ($entry in $lock.files) {
    $inputFile = if ($entry.name -eq 'ffmpeg.exe') { 'vendor/runtime/ffmpeg.exe' } else { Join-Path 'licenses' $entry.name }
    if ((Get-FileHash -LiteralPath $inputFile -Algorithm SHA256).Hash -ne $entry.sha256) { throw "Runtime diferente do lock: $($entry.name). Atualize os hashes somente após validar o novo build." }
    Copy-Item -LiteralPath $inputFile -Destination (Join-Path 'output' $entry.name) -Force
}
$sourceArchive = 'output/ffmpeg-8.0.1-source.tar.xz'
if (-not (Test-Path -LiteralPath $sourceArchive)) {
    $cachedSource = 'vendor/sources/ffmpeg-8.0.1.tar.xz'
    if (Test-Path -LiteralPath $cachedSource) { Copy-Item -LiteralPath $cachedSource -Destination $sourceArchive }
    else { Invoke-WebRequest 'https://ffmpeg.org/releases/ffmpeg-8.0.1.tar.xz' -OutFile $sourceArchive }
}
if ((Get-FileHash -LiteralPath $sourceArchive -Algorithm SHA256).Hash -ne '05ee0b03119b45c0bdb4df654b96802e909e0a752f72e4fe3794f487229e5a41') { throw 'Fonte correspondente do FFmpeg não passou no SHA256.' }
py -3.11 create_installer_art.py
if ($LASTEXITCODE -ne 0) { throw 'Arte do instalador falhou.' }
& ./build.ps1
py -3.11 build_installer.py
if ($LASTEXITCODE -ne 0) { throw 'MSI não foi gerado.' }
py -3.11 verify_installer.py
if ($LASTEXITCODE -ne 0) { throw 'MSI não passou na verificação.' }
& ./build_setup.ps1
$report = Join-Path $PSScriptRoot 'output/smoke.json'
$process = Start-Process -FilePath "$PSScriptRoot/output/Lume/TranscreveLocal/TranscreveLocal.exe" -ArgumentList @('--smoke-test','--smoke-report',('"'+$report+'"')) -PassThru -Wait -WindowStyle Hidden
if ($process.ExitCode -ne 0) { throw 'Teste do EXE falhou.' }
py -3.11 verify_installer_cycle.py
if ($LASTEXITCODE -ne 0) { throw 'Ciclo de instalação/remoção falhou.' }
Compress-Archive -Path output/Lume/TranscreveLocal -DestinationPath output/Lume-Windows-x64.zip -Force
$lines = Get-ChildItem output -File | Where-Object { $_.Extension -in '.exe','.msi','.zip','.xz' } | ForEach-Object {
    $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $($_.Name)"
}
$lines | Set-Content output/SHA256SUMS.txt -Encoding ASCII
Write-Output 'Distribuição gerada e validada em output/.'
