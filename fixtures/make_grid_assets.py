"""Generate original local image-grid fixture assets."""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw


SIZE = 128
GRID_DIR = Path(__file__).parent / "assets" / "grid"
LABELS = ("circle", "triangle", "square", "star")


def _background(rng: random.Random) -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE))
    pixels = image.load()
    for y in range(SIZE):
        for x in range(SIZE):
            noise = rng.randint(-16, 16)
            value = max(0, min(255, 150 + noise + (x + y) // 12))
            pixels[x, y] = (value, value, value)
    return image


def _draw_shape(image: Image.Image, label: str, rng: random.Random) -> None:
    draw = ImageDraw.Draw(image)
    color = (35, 76, 115)
    accent = (220, 235, 245)
    left = 27 + rng.randint(-4, 4)
    top = 27 + rng.randint(-4, 4)
    right = 101 + rng.randint(-4, 4)
    bottom = 101 + rng.randint(-4, 4)
    if label == "circle":
        draw.ellipse((left, top, right, bottom), fill=color, outline=accent, width=3)
    elif label == "triangle":
        draw.polygon(((64, top), (right, bottom), (left, bottom)), fill=color)
        draw.line(((64, top), (right, bottom), (left, bottom), (64, top)), fill=accent, width=3)
    elif label == "square":
        draw.rectangle((left, top, right, bottom), fill=color, outline=accent, width=3)
    elif label == "star":
        points = []
        for index in range(10):
            angle = -90 + index * 36
            radius = 38 if index % 2 == 0 else 17
            import math

            points.append((64 + radius * math.cos(math.radians(angle)),
                           64 + radius * math.sin(math.radians(angle))))
        draw.polygon(points, fill=color)
        draw.line(points + [points[0]], fill=accent, width=3)


def generate() -> dict[str, str]:
    GRID_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {}
    for index in range(16):
        label = LABELS[index % len(LABELS)]
        image = _background(random.Random(1000 + index))
        _draw_shape(image, label, random.Random(2000 + index))
        filename = f"tile_{index:02d}.png"
        image.save(GRID_DIR / filename)
        manifest[filename] = label
    (GRID_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    generated = generate()
    print(f"Generated {len(generated)} image-grid tiles in {GRID_DIR}")
