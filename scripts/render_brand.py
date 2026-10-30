"""Renderiza a capa do README com tipografia consistente em qualquer navegador."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SCALE = 2


def main():
    image = Image.new('RGB', (1600 * SCALE, 600 * SCALE), '#faf9f5')
    draw = ImageDraw.Draw(image)

    def font(name, size):
        return ImageFont.truetype(str(Path('C:/Windows/Fonts') / name), size * SCALE)

    def box(bounds, fill, radius=0):
        draw.rounded_rectangle(tuple(v * SCALE for v in bounds), radius=radius * SCALE, fill=fill)

    def text(position, value, face, size, color):
        draw.text(tuple(v * SCALE for v in position), value, font=font(face, size), fill=color, spacing=10 * SCALE)

    draw.ellipse((930 * SCALE, 44 * SCALE, 1530 * SCALE, 584 * SCALE), fill='#f0e7dc')
    shadow = Image.new('RGBA', image.size)
    ImageDraw.Draw(shadow).rounded_rectangle((972 * SCALE, 120 * SCALE, 1484 * SCALE, 504 * SCALE), radius=28 * SCALE, fill=(80, 57, 40, 24))
    image.paste(shadow.filter(ImageFilter.GaussianBlur(18 * SCALE)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(18 * SCALE)))
    draw = ImageDraw.Draw(image)
    box((960, 104, 1480, 488), '#ffffff', 28)
    text((100, 62), 'SUA VOZ TEM ESPAÇO AQUI.', 'seguisb.ttf', 22, '#a9583e')
    text((92, 118), 'Lume', 'georgia.ttf', 160, '#252522')
    text((102, 318), 'Suas gravações,\nem palavras.', 'seguisb.ttf', 49, '#35352f')
    text((104, 510), 'Transcrição local  ·  Windows  ·  Open source', 'segoeui.ttf', 24, '#79766c')
    text((1004, 137), 'GRAVAÇÃO  →  TEXTO', 'seguisb.ttf', 20, '#a9583e')
    heights = [12, 22, 34, 18, 44, 68, 48, 84, 62, 98, 72, 54, 80, 46, 60, 32, 44, 20, 28, 12]
    for index, height in enumerate(heights):
        x = 1007 + index * 22
        box((x, 253 - height / 2, x + 7, 253 + height / 2), '#c17c60', 4)
    box((1004, 329, 1436, 331), '#eee9e0')
    text((1004, 353), 'Tudo começa com\numa boa ideia.', 'segoeui.ttf', 29, '#393a34')
    text((1005, 449), 'PRONTO PARA REVISAR', 'seguisb.ttf', 16, '#8a877d')
    image.resize((1600, 600), Image.Resampling.LANCZOS).save(ROOT / 'docs/brand.png', optimize=True)


if __name__ == '__main__':
    main()
