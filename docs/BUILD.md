# Compilar o Lume

O usuário final não precisa executar estas etapas: baixe o Setup nas Releases. Este guia é para desenvolvimento e geração da distribuição.

## Windows

Use Windows x64, Python 3.11 de 64 bits com Tkinter e Microsoft Visual C++ Runtime. Para compilar o Setup é usado o compilador .NET Framework que acompanha o ambiente Windows de build. A CI usa Windows Server 2022; a aplicação tem como alvo Windows 10/11 x64.

```powershell
py -3.11 -m pip install -r requirements-build.txt
.\prepare.ps1
py -3.11 -m unittest discover -s tests -v
.\release.ps1
```

`prepare.ps1` baixa os motores fixados em versão/hash, inclui os backends de CPU e os runtimes e verifica se executam. `release.ps1` testa e gera `output/Lume-Setup.exe`, `output/Lume-Windows-x64.msi`, `output/Lume-Windows-x64.zip` e `output/SHA256SUMS.txt`.

O modo de compilação da CI recebe o FFmpeg produzido pelo job Linux com `prepare.ps1 -FFmpeg caminho\ffmpeg.exe`. Os arquivos `FFmpeg-LGPL-2.1.txt` e `FFmpeg-build.txt` devem acompanhar o binário.

## Recompilar FFmpeg

Em Ubuntu com `make`, `nasm`, `gcc-mingw-w64-x86-64` e `g++-mingw-w64-x86-64`:

```bash
bash scripts/build_ffmpeg.sh
```

O script verifica SHA256 da fonte oficial, compila para Windows x64 e gera a conversão de áudio usada pelo Lume. Não requer bibliotecas externas de codecs, drivers ou rede durante o uso. Os decodificadores incluídos são listados na receita; a saída é WAV PCM mono para o Whisper.

## Releases

O workflow do repositório executa testes e publica artifacts de compilação. Tags `v*` geram uma release com os pacotes e fontes correspondentes. Para mudar a versão, atualize `version.py` e o `PRODUCT_CODE` no instalador. Preserve `UPGRADE_CODE`, GUIDs dos componentes existentes e a pasta `%LOCALAPPDATA%\TranscreveLocal`.

Não versionar `vendor`, modelos, mídia, logs ou arquivos de saída. Não publicar o executável sem passar no smoke test e sem os avisos/fontes dos componentes de terceiros.

Ao trocar a versão ou a receita do FFmpeg, valide o binário produzido e atualize os hashes em `runtime-lock.json`. A release verifica se os arquivos empacotados correspondem ao lock e inclui o arquivo-fonte oficial. Os hashes fixam o runtime da release; não são uma promessa de binários idênticos em compiladores diferentes.
