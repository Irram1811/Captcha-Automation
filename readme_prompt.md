README task. Edit README.md only. Do not run commands. Do not invent any number.

Write README.md with:
1. Purpose and scope: a QA harness for SELF-HOSTED test pages listed in
   config/targets.yaml (127.0.0.1 only), enforced by an allowlist; unknown or
   unsupported widgets are SKIPPED and routed to human review; not for
   production sites or third-party CAPTCHAs.
2. Architecture (ASCII): CLI -> pipeline (deterministic) / agent loop (LLM) ->
   shared TOOL_REGISTRY -> Playwright; evidence (screenshots, events.jsonl,
   trace.zip, report.json/md).
3. Directory tree as it exists now (read the repo; do not guess).
4. macOS setup with uv and Python 3.11, one command per line, no comment lines.
5. Run commands: ./scripts/bootstrap.sh, ./scripts/run_demo.sh, the two-terminal
   alternative, agent-mode commands (--mode agent --mock, and --mode agent with
   ANTHROPIC_API_KEY), and python -m playwright show-trace runs/<run folder>/trace.zip.
6. A results table copied EXACTLY from the measurements below, then these caveats:
   image_grid with the fake classifier uses a harness-side oracle and measures
   click/verify logic, not vision accuracy; all numbers are on self-hosted
   fixtures only; the slider match score is about 0.65, so a different
   background may behave differently.
7. Troubleshooting table: ModuleNotFoundError; address already in use
   (lsof -t -iTCP:8765 -sTCP:LISTEN | xargs kill -9); ERR_CONNECTION_REFUSED;
   broken slider picture (open it through the server, not as a file); zsh
   "unknown sort specifier" (do not paste lines starting with #); the pytest
   "Bare functions are deprecated" warning is harmless.
8. Requirements checklist mapping each original requirement (open allowlisted
   page, detect widget, solve with the right tool, verify independently, report
   with evidence, agent mode, deterministic mode) to the file that implements it.

REAL MEASUREMENTS (runs/rates.md):
# Fixture Measurement Rates

| Widget | Classifier | Runs | Successes | Rate | Median duration (s) | Failed seeds |
|---|---|---:|---:|---:|---:|---|
| slider | — | 20 | 20 | 100.00% | 1.255 | [] |
| image_grid | fake | 20 | 20 | 100.00% | 1.655 | [] |

Caveats: Fake image-grid mode uses the generated manifest as a harness-side oracle and measures the click/verify pipeline, not vision accuracy. All measurements cover only self-hosted fixtures.

Sanity expectation: fake image-grid mode should be 20/20; this is a note, not a gate.

REAL SUMMARY (runs/summary.md):
# CAPTCHA Run Summary

| Target | Mode | Widget detected | Tool used | Verdict | Attempts | Duration | Report |
|---|---|---|---|---|---:|---:|---|
| `local_checkbox` | `deterministic` | `checkbox` | `click_checkbox` | **PASS** | 0 | 0.673s | [2026-10-25T16-52-11_local_checkbox](./2026-10-25T16-52-11_local_checkbox/report.md) |
| `local_slider` | `deterministic` | `slider` | `solve_slider` | **PASS** | 1 | 1.438s | [2026-10-25T16-52-12_local_slider](./2026-10-25T16-52-12_local_slider/report.md) |
| `local_imagegrid` | `deterministic` | `image_grid` | `solve_image_grid` | **SKIPPED** | 0 | 0.383s | [2026-10-25T16-52-13_local_imagegrid](./2026-10-25T16-52-13_local_imagegrid/report.md) |
| `local_none` | `deterministic` | `none` | `skip` | **SKIPPED** | 0 | 0.285s | [2026-10-25T16-52-14_local_none](./2026-10-25T16-52-14_local_none/report.md) |

Hand-off: tell me which commands to run, for example: head -80 README.md
