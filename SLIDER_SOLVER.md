# Slider solver notes

The solver is intentionally visual: it matches Canny edge maps with OpenCV
template matching and never reads the fixture's hidden `data-gap-x` attribute.
It converts image coordinates to CSS track travel, then performs an eased drag
with jitter and a small endpoint correction.

Known failure modes:

- Strong lighting changes, busy backgrounds, or image noise can create a false
  high-scoring edge match.
- CSS zoom, device-pixel-ratio differences, or responsive resizing can make the
  natural PNG and rendered screenshot scales differ. The matcher accepts a
  scale factor, but extreme scaling can still lose edge detail.
- Piece shadows, anti-aliasing, transparency handling, and border changes can
  weaken template correlation.
- The configured retry limit bounds recovery; each retry captures fresh pixels
  and records its predicted offset and confidence in `events.jsonl`.

The confidence score is evidence for orchestration, not a guarantee that the
slider was solved. Final success is independently checked by `verify_result`.
