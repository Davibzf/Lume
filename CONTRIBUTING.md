# Contribuindo com o Lume

Obrigado por ajudar a tornar a transcrição local mais acessível.

1. Abra uma issue descrevendo o problema ou a mudança proposta.
2. Crie uma branch e mantenha a alteração focada.
3. Use Python 3.11 de 64 bits no Windows. O aplicativo usa a biblioteca padrão; dependências de empacotamento estão em `requirements-build.txt`.
4. Execute `py -3.11 -m unittest discover -s tests -v`.
5. Para mudanças na integração Windows, execute também o EXE com `--smoke-test --smoke-report report.json`. O teste cobre drops assíncronos no loop real da interface.
6. Envie um pull request explicando o problema, a solução e como verificou.

Não envie arquivos de áudio pessoais, transcrições, modelos, tokens, logs de usuários ou executáveis no Git. Utilize mídia sintética nos testes. Não adicione uploads de mídia nem serviços de transcrição remotos ao fluxo local.

Para gerar a distribuição, siga [o guia de compilação](docs/BUILD.md). Mudanças no instalador devem preservar `UpgradeCode`, diretórios dos modelos e dados do usuário.
