# Mídia sintética

Estes três arquivos contêm somente um tom de 880 Hz de um segundo. O MP4 inclui uma imagem preta de 160×90. Não há voz, dados pessoais nem conteúdo de terceiros.

Gerados com FFmpeg (uma distribuição com os encoders MP3/AAC e MPEG-4):

```text
ffmpeg -f lavfi -i sine=frequency=880:duration=1 -c:a libmp3lame tone.mp3
ffmpeg -f lavfi -i sine=frequency=880:duration=1 -c:a aac tone.m4a
ffmpeg -f lavfi -i color=c=black:s=160x90:d=1 -f lavfi -i sine=frequency=880:duration=1 -c:v mpeg4 -c:a aac -shortest tone.mp4
```

São dados de teste do projeto, distribuídos sob a licença MIT. O teste confirma conversão para PCM mono 16 kHz com o FFmpeg da distribuição.
