# Publicação inicial

Publicar somente código e assets próprios/licenciados; excluir runtime, modelos, logs, mídia e resultados locais. Manter identidade MSI e modelos da versão anterior. Entrega Windows x64; não anunciar compatibilidade universal.

1. Documentação, MIT, política de segurança e contribuição.
2. Preparação reprodutível de Whisper com SHA256 e backends x64; FFmpeg LGPL compilado de fonte oficial sem dependências externas.
3. CI para testar, empacotar e anexar fontes/licenças/hashes junto aos executáveis.
4. Bootstrapper EXE com MSI incorporado e verificado, executado sem elevação por padrão.
5. Testes locais e pipeline; publicação da primeira release com EXE, MSI e portátil.

As verificações do Windows e as permissões da conta GitHub serão respeitadas. Não publicar pacotes com fontes de terceiros incompletos ou dados pessoais.
