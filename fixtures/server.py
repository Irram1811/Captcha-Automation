"""Serve the self-hosted fixtures on loopback only."""

import argparse
import errno
import io
import random
from pathlib import Path

from aiohttp import web
from PIL import Image, ImageDraw

from .make_assets import gap_polygon, make_background, make_piece


MIN_GAP, MAX_GAP = 60, 240
_SLIDER_CACHE: dict[int, tuple[bytes, bytes]] = {}


def _gap_x(seed: int) -> int:
    return MIN_GAP + (abs(seed) % (MAX_GAP - MIN_GAP + 1))


def _png_response(image: Image.Image) -> web.Response:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return web.Response(body=output.getvalue(), content_type="image/png")


def _png_bytes(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _slider_images(seed: int) -> tuple[bytes, bytes]:
    cached = _SLIDER_CACHE.get(seed)
    if cached is not None:
        return cached
    background = make_background(random.Random(seed))
    _draw_gap(background, _gap_x(seed))
    piece = make_piece(make_background(random.Random(seed)))
    cached = (_png_bytes(background), _png_bytes(piece))
    _SLIDER_CACHE[seed] = cached
    return cached


def _draw_gap(image: Image.Image, gap_x: int) -> None:
    draw = ImageDraw.Draw(image)
    points = gap_polygon(gap_x)
    draw.polygon(points, fill=(28, 62, 93))
    draw.line(points + [points[0]], fill=(220, 240, 255), width=2)


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(Path(__file__).parent / "index.html")


async def slider_background(request: web.Request) -> web.Response:
    seed = int(request.query.get("seed", "0"))
    background, _ = _slider_images(seed)
    return web.Response(body=background, content_type="image/png")


async def slider_piece(request: web.Request) -> web.Response:
    seed = int(request.query.get("seed", "0"))
    _, piece = _slider_images(seed)
    return web.Response(body=piece, content_type="image/png")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/assets/slider_bg.png", slider_background)
    app.router.add_get("/assets/slider_piece.png", slider_piece)
    app.router.add_static("/", Path(__file__).parent, show_index=True)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve CAPTCHA fixture pages")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        web.run_app(create_app(), host="127.0.0.1", port=args.port)
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise SystemExit(
                f"Port {args.port} is already in use. Check it with "
                f"'lsof -nP -iTCP:{args.port} -sTCP:LISTEN', stop the stale process, "
                "and start the server again."
            ) from exc
        raise


if __name__ == "__main__":
    main()
