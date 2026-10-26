"""Deterministic CAPTCHA widget detection heuristics."""

from pydantic import BaseModel, ConfigDict

from ..models import Detection, ToolResult
from .context import RunContext


class DetectWidgetArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def tool(ctx: RunContext, **args) -> ToolResult:
    DetectWidgetArgs.model_validate(args)
    matches = await ctx.page.evaluate(
        """() => {
          const visible = (el) => {
            const rect = el.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
          };
          const text = (el) => (el.textContent || '').replace(/\\s+/g, ' ').trim();
          const selector = (el) => {
            if (el.id) return `#${CSS.escape(el.id)}`;
            if (el.classList.length) {
              return `${el.tagName.toLowerCase()}.${[...el.classList].map(CSS.escape).join('.')}`;
            }
            return el.tagName.toLowerCase();
          };
          const checkbox = [...document.querySelectorAll('[role="checkbox"]')]
            .filter(visible).map(selector);
          const robotText = [...document.querySelectorAll('body *')]
            .find((el) => visible(el) && /not\\s+a\\s+robot/i.test(text(el)));
          const frames = [...document.querySelectorAll('iframe')]
            .filter((el) => /captcha|recaptcha|hcaptcha/i.test(el.src));
          const challengeFrames = [...document.querySelectorAll('iframe')]
            .filter((el) => /captcha|challenge/i.test(`${el.src} ${el.title}`));
          const challengeContainers = [...document.querySelectorAll(
            '[id*="challenge" i], [class*="challenge" i]'
          )].filter(visible).map(selector);
          const humanText = [...document.querySelectorAll('body *')]
            .find((el) => visible(el) && /verify\\s+you\\s+are\\s+human|security\\s+challenge/i.test(text(el)));
          const handles = [...document.querySelectorAll(
            '[draggable="true"], [role="slider"], input[type="range"], button'
          )].filter(visible);
          const tracks = [...document.querySelectorAll(
            '[id*="track" i], [class*="track" i], [role="slider"]'
          )].filter(visible);
          const pieces = [...document.querySelectorAll(
            'canvas, img[src*="piece" i], [id*="piece" i], [class*="piece" i]'
          )].filter(visible);
          const prompts = [...document.querySelectorAll('body *')]
            .filter((el) => visible(el) && /select\\s+all\\s+squares\\s+with/i.test(text(el)));
          const prompt = prompts.sort((a, b) => text(a).length - text(b).length)[0] || null;
          const clickable = [...document.querySelectorAll(
            'button, [role="button"], [role="checkbox"]'
          )].filter(visible);
          const imageTiles = [...document.querySelectorAll('img')]
            .filter((el) => visible(el) && !el.closest('button,[role="button"],[role="checkbox"]'));
          const candidates = clickable.length ? clickable : imageTiles;
          const dimensions = (el) => {
            const rect = el.getBoundingClientRect();
            return { width: rect.width, height: rect.height };
          };
          const groups = [];
          for (const candidate of candidates) {
            const size = dimensions(candidate);
            if (size.width < 20 || size.height < 20) continue;
            const group = candidates.filter((other) => {
              const otherSize = dimensions(other);
              return Math.abs(otherSize.width - size.width) <= 4 &&
                Math.abs(otherSize.height - size.height) <= 4;
            });
            if (group.length >= 9 && group.length <= 16) groups.push(group);
          }
          const tileGroup = groups.sort((a, b) => b.length - a.length)[0] || [];
          const tileContainer = tileGroup[0] ? tileGroup[0].parentElement : null;
          const verifyControls = [...document.querySelectorAll(
            'button, input[type="submit"], [role="button"]'
          )].filter((el) => visible(el) && /\\b(verify|submit|check)\\b/i.test(text(el)));
          const gridVerify = verifyControls.find((control) => {
            if (!tileContainer) return false;
            const scope = tileContainer.closest('main,section,form');
            return control.parentElement === tileContainer ||
              (scope && control.closest('main,section,form') === scope);
          }) || null;
          const imageGrid = {
            promptSelector: prompt ? selector(prompt) : null,
            prompt: prompt ? text(prompt) : null,
            tileSelector: tileGroup.length ? selector(tileGroup[0]) : null,
            tileSelectors: tileGroup.map(selector),
            tileCount: tileGroup.length,
            verifySelector: gridVerify ? selector(gridVerify) : null,
            challengeSignals: Boolean(prompt || tileGroup.length || verifyControls.length)
          };
          return {
            checkbox,
            robotText: robotText ? selector(robotText) : null,
            captchaFrames: frames.map((el) => el.src),
            challengeFrames: challengeFrames.map(selector),
            challengeContainers,
            humanText: humanText ? selector(humanText) : null,
            handles: handles.map(selector),
            tracks: tracks.map(selector),
            pieces: pieces.map(selector),
            imageGrid
          };
        }"""
    )
    grid = matches["imageGrid"]
    prompt_match = bool(grid["promptSelector"])
    tile_match = 9 <= grid["tileCount"] <= 16
    verify_match = bool(grid["verifySelector"])
    grid_signals = sum((prompt_match, tile_match, verify_match))
    if grid_signals == 3:
        evidence = [
            f"prompt selector: {grid['promptSelector']}",
            f"prompt: {grid['prompt']}",
            f"tile selector: {grid['tileSelector']}",
            f"tile selectors: {grid['tileSelectors']}",
            f"tile count: {grid['tileCount']}",
            f"verify selector: {grid['verifySelector']}",
        ]
        detection = Detection(widget="image_grid", confidence=0.97, evidence=evidence)
    elif grid_signals == 2:
        evidence = [
            f"prompt selector: {grid['promptSelector']}",
            f"prompt: {grid['prompt']}",
            f"tile selector: {grid['tileSelector']}",
            f"tile count: {grid['tileCount']}",
            f"verify selector: {grid['verifySelector']}",
        ]
        detection = Detection(widget="image_grid", confidence=0.60, evidence=evidence)
    elif matches["checkbox"] or matches["robotText"] or matches["captchaFrames"]:
        evidence = [
            f"role=checkbox: {matches['checkbox']}",
            f"robot text: {matches['robotText']}",
            f"captcha iframes: {matches['captchaFrames']}",
        ]
        detection = Detection(widget="checkbox", confidence=0.98, evidence=evidence)
    elif matches["handles"] and matches["tracks"] and matches["pieces"]:
        evidence = [
            f"handles: {matches['handles']}",
            f"tracks: {matches['tracks']}",
            f"pieces: {matches['pieces']}",
        ]
        detection = Detection(widget="slider", confidence=0.95, evidence=evidence)
    elif matches["challengeFrames"] or matches["challengeContainers"] or matches["humanText"]:
        evidence = [
            f"captcha challenge iframes: {matches['challengeFrames']}",
            f"challenge containers: {matches['challengeContainers']}",
            f"human verification text: {matches['humanText']}",
        ]
        detection = Detection(widget="unknown", confidence=0.55, evidence=evidence)
    else:
        detection = Detection(widget="none", confidence=0.99, evidence=["No checkbox, slider, or image-grid signatures matched"])
    ctx.detection = detection
    ctx.evidence.log_event("detect_widget", detection.model_dump())
    return ToolResult(ok=True, data=detection.model_dump())
