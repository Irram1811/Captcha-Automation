"""Generate the local slider fixture's deterministic PNG assets."""

from pathlib import Path
import random

from PIL import Image, ImageDraw

WIDTH, HEIGHT, PIECE = 320, 160, 52
OUT = Path(__file__).parent / "assets"


def gap_polygon(x: int, y: int = 54) -> list[tuple[int, int]]:
    return [(x + 10, y), (x + PIECE - 10, y), (x + PIECE - 10, y + 12),
            (x + PIECE, y + 20), (x + PIECE - 10, y + 28), (x + PIECE - 10, y + PIECE),
            (x + 10, y + PIECE), (x + 10, y + 38), (x, y + 30), (x + 10, y + 22)]


def make_background(rng: random.Random | None = None) -> Image.Image:
    rng = rng or random.Random(7)
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            noise = rng.randrange(-8, 9)
            pixels[x, y] = (max(0, 45 + x // 3 + noise), max(0, 105 + y // 2 + noise), max(0, 150 + noise))
    draw = ImageDraw.Draw(image)
    draw.ellipse((35, 18, 125, 108), fill=(225, 180, 88), outline=(255, 220, 130), width=3)
    draw.rectangle((190, 20, 285, 130), fill=(46, 125, 95), outline=(110, 190, 130), width=4)
    return image


def make_piece(background: Image.Image) -> Image.Image:
    piece = Image.new("RGBA", (PIECE, PIECE), (0, 0, 0, 0))
    mask = Image.new("L", (PIECE, PIECE), 0)
    ImageDraw.Draw(mask).polygon([(x - 180, y - 54) for x, y in gap_polygon(180)], fill=255)
    ImageDraw.Draw(piece).polygon([(x - 180, y - 54) for x, y in gap_polygon(180)], fill=(28, 62, 93, 255))
    ImageDraw.Draw(piece).line([(x - 180, y - 54) for x, y in gap_polygon(180)] + [(10, 0)], fill=(220, 240, 255, 255), width=2)
    return piece


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    background = make_background()
    background.save(OUT / "slider_bg.png")
    make_piece(background).save(OUT / "slider_piece.png")
    print(f"Generated {OUT / 'slider_bg.png'} and {OUT / 'slider_piece.png'}")
