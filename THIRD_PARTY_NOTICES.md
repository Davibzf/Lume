# Componentes de terceiros

A licença MIT do Lume cobre apenas seu código e assets próprios. Os seguintes componentes conservam suas licenças:

| Componente | Licença | Origem |
|---|---|---|
| whisper.cpp 1.9.2 e GGML | MIT | https://github.com/ggml-org/whisper.cpp/tree/v1.9.2 |
| Modelos Whisper, baixados separadamente | MIT | https://github.com/openai/whisper |
| FFmpeg 8.0.1 da distribuição oficial Lume | LGPL-2.1-or-later | https://ffmpeg.org/releases/ffmpeg-8.0.1.tar.xz |
| Python | PSF | https://www.python.org/psf/license/ |
| Tcl/Tk | Licenças próprias permissivas | Licenças fornecidas pelo empacotador em `_internal` |
| PyInstaller | GPL com exceção para os aplicativos empacotados | https://pyinstaller.org/en/stable/license.html |
| Microsoft Visual C++ Runtime | Termos Microsoft | https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist |
| .NET Framework, usado pelo Setup | Componente do Windows, termos Microsoft | Não é incorporado ao pacote |

O FFmpeg é executado como programa separado. A versão da release é compilada com `scripts/build_ffmpeg.sh`, sem bibliotecas externas de codecs, sem componentes GPL e com instruções x86-64 básicas e detecção de CPU em tempo de execução. O código-fonte correspondente, a receita de compilação e os avisos de licença acompanham a mesma release. Não substitua esse binário por outra distribuição sem atualizar as licenças e a oferta dos fontes correspondentes.

Licenças em `licenses/` também são incluídas no aplicativo distribuído. O download dos modelos requer acesso ao Hugging Face; os modelos não são incorporados ao instalador.
