"""Gera apenas a arte de distribuição; Pillow não é necessário no aplicativo."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def main():
    scale = 2
    image = Image.new('RGB', (560 * scale, 360 * scale), '#faf9f5')
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 165 * scale - 1, 360 * scale), fill='#252522')
    fonts = Path('C:/Windows/Fonts')
    title = ImageFont.truetype(str(fonts / 'georgia.ttf'), 25 * scale)
    small = ImageFont.truetype(str(fonts / 'segoeui.ttf'), 9 * scale)
    for x, top, bottom in [(31, 43, 57), (41, 34, 66), (51, 25, 75), (61, 37, 63), (71, 46, 54)]:
        draw.line((x * scale, top * scale, x * scale, bottom * scale), fill='#d1876b', width=4 * scale)
        for y in (top, bottom):
            draw.ellipse(((x - 2) * scale, (y - 2) * scale, (x + 2) * scale, (y + 2) * scale), fill='#d1876b')
    draw.text((26 * scale, 108 * scale), 'Lume', font=title, fill='#f8f5ed')
    draw.text((27 * scale, 149 * scale), 'TRANSCRIÇÃO LOCAL', font=small, fill='#d5a48d')
    draw.multiline_text((27 * scale, 183 * scale), 'Menos esforço.\nMais palavras.', font=small, fill='#c8c3b9', spacing=6 * scale)
    draw.line((27 * scale, 281 * scale, 137 * scale, 281 * scale), fill='#50463e', width=scale)
    draw.text((27 * scale, 298 * scale), 'ÁUDIO  →  TEXTO', font=small, fill='#d5a48d')
    draw.line((195 * scale, 309 * scale, 525 * scale, 309 * scale), fill='#e5dfd5', width=scale)
    destination = Path(__file__).parent / 'assets/installer'
    destination.mkdir(parents=True, exist_ok=True)
    image.save(destination / 'backdrop.bmp')


if __name__ == '__main__':
    main()
