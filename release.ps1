$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
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
