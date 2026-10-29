param([string]$Python = 'py', [string]$Output = "$PSScriptRoot\output\Lume")
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path 'vendor/runtime/whisper-cli.exe')) { throw 'Execute prepare.ps1 antes de compilar.' }
$pythonArgs = @()
if ($Python -eq 'py') { $pythonArgs = @('-3.11') }
& $Python @pythonArgs -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Testes falharam.' }
& $Python @pythonArgs -m PyInstaller --noconfirm --clean --windowed --onedir --name TranscreveLocal --icon 'assets/transcreve.ico' --distpath $Output --workpath "$PSScriptRoot/build" --add-data 'assets;assets' --add-data 'vendor/runtime;runtime' --add-data 'licenses;licenses' app.py
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar executável.' }
Copy-Item README.md (Join-Path $Output 'TranscreveLocal/LEIA-ME.md') -Force
Copy-Item VALIDACAO.md (Join-Path $Output 'TranscreveLocal/VALIDACAO.md') -Force
Copy-Item LICENSE (Join-Path $Output 'TranscreveLocal/LICENSE.txt') -Force
Copy-Item THIRD_PARTY_NOTICES.md (Join-Path $Output 'TranscreveLocal/THIRD_PARTY_NOTICES.md') -Force
Write-Output "Aplicativo gerado em $Output\TranscreveLocal\TranscreveLocal.exe"
