"""OpenCV-based slider gap localization."""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class GapResult:
    x: int
    confidence: float


def _decode(data: bytes, flags: int) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), flags)
    if image is None:
        raise ValueError("Could not decode PNG image")
    return image


def _edges(image: np.ndarray) -> np.ndarray:
    if image.ndim == 3 and image.shape[2] == 4:
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
        alpha = image[:, :, 3]
        edge = cv2.Canny(gray, 50, 150)
        edge = cv2.bitwise_or(edge, cv2.Canny(alpha, 50, 150))
        return edge
    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Canny(gray, 50, 150)


def find_gap_offset(bg_png: bytes, piece_png: bytes, scale: float = 1.0) -> GapResult:
    """Find the piece's best horizontal match in the background.

    ``scale`` maps the piece's natural pixels to the background image pixels. The
    returned ``x`` is the left edge of the match in background-image pixels.
    """
    if scale <= 0:
        raise ValueError("scale must be greater than zero")
    background = _decode(bg_png, cv2.IMREAD_COLOR)
    piece = _decode(piece_png, cv2.IMREAD_UNCHANGED)
    # Browser screenshots preserve transparent pixels around the piece. Remove
    # that padding so black/transparent borders do not dominate correlation.
    if piece.ndim == 3 and piece.shape[2] == 4:
        alpha = piece[:, :, 3]
        points = cv2.findNonZero((alpha > 8).astype(np.uint8))
        if points is not None:
            x, y, width, height = cv2.boundingRect(points)
            piece = piece[y:y + height, x:x + width]
    if scale != 1.0:
        piece = cv2.resize(piece, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    bg_edges = _edges(background)
    piece_edges = _edges(piece)
    kernel = np.ones((2, 2), dtype=np.uint8)
    bg_edges = cv2.dilate(bg_edges, kernel)
    piece_edges = cv2.dilate(piece_edges, kernel)
    ph, pw = piece_edges.shape[:2]
    bh, bw = bg_edges.shape[:2]
    if ph > bh or pw > bw:
        raise ValueError("Scaled piece is larger than the background")
    # A sparse alpha edge can produce weak correlations; keep the template's
    # actual edge pixels while matching against the complete background edge map.
    if not np.any(piece_edges):
        raise ValueError("Piece image contains no detectable edges")
    scores = cv2.matchTemplate(bg_edges, piece_edges, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, location = cv2.minMaxLoc(scores)
    return GapResult(x=int(location[0]), confidence=float(confidence))
