import cv2
import numpy as np

from captcha_agent.vision.slider_gap import find_gap_offset


def _png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def test_find_gap_offset_known_position():
    background = np.zeros((120, 320, 3), dtype=np.uint8)
    x, y = 143, 32
    cv2.rectangle(background, (x + 8, y + 8), (x + 42, y + 42), (255, 255, 255), 2)
    cv2.circle(background, (x + 26, y + 26), 8, (255, 255, 255), 2)
    piece = background[y:y + 52, x:x + 52]
    result = find_gap_offset(_png(background), _png(piece))
    assert abs(result.x - x) <= 3
    assert result.confidence > 0.5


def test_find_gap_offset_handles_scale_factor():
    background = np.zeros((160, 320, 3), dtype=np.uint8)
    x, y = 187, 54
    cv2.rectangle(background, (x + 10, y), (x + 42, y + 52), (255, 255, 255), 2)
    natural_piece = cv2.resize(background[y:y + 52, x:x + 52], (26, 26), interpolation=cv2.INTER_AREA)
    result = find_gap_offset(_png(background), _png(natural_piece), scale=2.0)
    assert abs(result.x - x) <= 3
