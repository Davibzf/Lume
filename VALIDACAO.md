# Validação

Os testes automatizados cobrem download verificado, cancelamento, proteção de mídia original, exportação, interface, redimensionamento, progresso e arrastar/soltar.

## Regressão do arrastar e soltar

Uma mensagem WM_DROPFILES entregue durante Tk.mainloop causava falha fatal quando o callback nativo chamava Tk. O callback agora publica os arquivos na fila; App.poll atualiza a interface. O teste em subprocesso reproduziu o fechamento antes da correção e passou depois.

O modo `--smoke-test` do EXE usa vinte mensagens assíncronas alternando áudio e vídeo, nomes com espaços/acentos, preservação do editor e verificação de seleção final. Não utiliza gravações pessoais.

## Instaladores

`verify_installer.py` confere arquivos, arquitetura, versão, atalhos, ordem da confirmação e preservação dos modelos. `verify_installer_cycle.py` instala e remove um produto mínimo de teste com identificadores isolados, sem modificar a instalação real. `Lume-Setup.exe --verify` valida o MSI incorporado sem instalar.

## Limites

O computador de desenvolvimento é Windows x64 com Ryzen 5 5500 e 16 GB. Não há ensaio físico em todas as gerações de CPU, Windows ARM64, computadores de 32 bits ou outros sistemas. O gesto manual do Explorador não substitui os testes de mensagem nativa; a inspeção automatizada da interface do msiexec é bloqueada pela ferramenta utilizada.
