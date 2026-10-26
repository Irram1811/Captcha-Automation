# captcha-agent

`captcha-agent` is a QA harness for self-hosted CAPTCHA-like test pages listed
in `config/targets.yaml`. The allowlist enforces the configured scheme, host,
and port; the supplied targets are loopback-only (`127.0.0.1`). Unknown or
unsupported widgets are skipped and routed to human review. This project is not
for production sites and does not interact with third-party CAPTCHA providers.

## Architecture

```text
CLI / python -m captcha_agent
              |
              +--> deterministic pipeline
              |          |
              +--> agent loop (LLM)
                         |
                    shared TOOL_REGISTRY
                         |
                      Playwright
                         |
       screenshots / events.jsonl / trace.zip
                    report.json / report.md
```

Both execution modes use the same registered tools. The deterministic pipeline
chooses the tool from the detected widget. The agent loop chooses from the same
schemas after observing the page. `verify_result` independently evaluates the
configured success rule.

## Directory tree

```text
captcha-agent/
├── README.md
├── Makefile
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── config/
│   ├── targets.yaml
│   └── settings.yaml
├── fixtures/
│   ├── __init__.py
│   ├── index.html
│   ├── checkbox.html
│   ├── slider.html
│   ├── imagegrid.html
│   ├── none.html
│   ├── workflow.html
│   ├── make_assets.py
│   ├── make_grid_assets.py
│   ├── server.py
│   └── assets/
│       ├── slider_bg.png
│       ├── slider_piece.png
│       └── grid/
│           ├── manifest.json
│           └── tile_00.png ... tile_15.png
├── scripts/
│   ├── bootstrap.sh
│   ├── debug_slider.py
│   ├── measure_rates.py
│   └── run_demo.sh
├── src/captcha_agent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── allowlist.py
│   ├── browser.py
│   ├── evidence.py
│   ├── models.py
│   ├── pipeline.py
│   ├── report.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── context.py
│   │   ├── open_target.py
│   │   ├── observe.py
│   │   ├── detect_widget.py
│   │   ├── click_checkbox.py
│   │   ├── solve_slider.py
│   │   ├── slider_drag.py
│   │   ├── solve_image_grid.py
│   │   ├── verify_result.py
│   │   └── finish.py
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── slider_gap.py
│   │   └── tile_classifier.py
│   └── agent/
│       ├── __init__.py
│       ├── llm_client.py
│       ├── prompts.py
│       └── loop.py
├── tests/
│   ├── conftest.py
│   ├── test_allowlist.py
│   ├── test_browser_evidence.py
│   ├── test_detect_widget.py
│   ├── test_slider_gap.py
│   ├── test_slider_e2e.py
│   ├── test_tools.py
│   ├── test_agent_loop.py
│   ├── test_tile_classifier.py
│   ├── test_solve_image_grid.py
│   ├── test_verdicts.py
│   └── test_measure_rates_merge.py
└── runs/
    └── generated reports, traces, screenshots, and rates
```

## macOS setup

Run one command per line from the project root:

```bash
cd /Users/irramfatima/Desktop/captch/captcha-agent
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e .
uv pip install pytest pytest-asyncio
python -m playwright install chromium
python fixtures/make_assets.py
python fixtures/make_grid_assets.py
```

## Running the project

The bundled scripts perform setup and the local demo:

```bash
./scripts/bootstrap.sh
./scripts/run_demo.sh
```

Two-terminal alternative:

Terminal 1:

```bash
python -m fixtures.server --port 8765
```

Terminal 2:

```bash
python -m captcha_agent run-all --mode deterministic
```

For the local agent loop without an API key:

```bash
python -m captcha_agent run --target local_checkbox --mode agent --mock
python -m captcha_agent run-all --mode agent --mock
```

For Anthropic agent mode:

```bash
export ANTHROPIC_API_KEY=your-key
export LLM_MODEL=claude-3-5-sonnet-latest
python -m captcha_agent run --target local_checkbox --mode agent
```

Open a recorded trace with:

```bash
python -m playwright show-trace runs/<run folder>/trace.zip
```

## Measured results

The following table is copied exactly from the real `runs/rates.md` output:

| Widget | Classifier | Runs | Successes | Rate | Median duration (s) | Failed seeds |
|---|---|---:|---:|---:|---:|---|
| slider | — | 20 | 20 | 100.00% | 1.299 | [] |
| image_grid | fake | 20 | 20 | 100.00% | 1.646 | [] |

Caveats: Fake image-grid mode uses the generated manifest as a harness-side
oracle and measures the click/verify pipeline, not vision accuracy. All
measurements cover only self-hosted fixtures. The slider match score is about
0.65, so a different background may behave differently.

The following table is copied exactly from the real `runs/summary.md` output:

| Target | Mode | Widget detected | Tool used | Verdict | Attempts | Duration | Report |
|---|---|---|---|---|---:|---:|---|
| `local_checkbox` | `deterministic` | `checkbox` | `click_checkbox` | **PASS** | 0 | 1.019s | [2026-10-25T16-43-27_local_checkbox](./2026-10-25T16-43-27_local_checkbox/report.md) |
| `local_slider` | `deterministic` | `slider` | `solve_slider` | **PASS** | 1 | 1.282s | [2026-10-25T16-43-28_local_slider](./2026-10-25T16-43-28_local_slider/report.md) |
| `local_imagegrid` | `deterministic` | `image_grid` | `solve_image_grid` | **FAIL** | 0 | 0.382s | [2026-10-25T16-43-29_local_imagegrid](./2026-10-25T16-43-29_local_imagegrid/report.md) |
| `local_none` | `deterministic` | `none` | `skip` | **SKIPPED** | 0 | 0.291s | [2026-10-25T16-43-30_local_none](./2026-10-25T16-43-30_local_none/report.md) |

The summary reflects the run before the missing-classifier verdict was changed
to `SKIPPED`; the measurement table is independent and records fake-classifier
successes.

## Troubleshooting

| Symptom | Action |
|---|---|
| `ModuleNotFoundError` | Run from the project root with `.venv` active; install with `uv pip install -e .`. |
| Address already in use | Run `lsof -t -iTCP:8765 -sTCP:LISTEN | xargs kill -9`. |
| `ERR_CONNECTION_REFUSED` | The fixture server is not running; start `python -m fixtures.server --port 8765`. |
| Broken slider picture | Open `http://127.0.0.1:8765/slider.html?seed=1` through the running server, not as a file. |
| zsh `unknown sort specifier` | Do not paste lines starting with `#` into zsh. |
| pytest `Bare functions are deprecated` warning | This warning is harmless; it does not indicate a test failure. |

## Requirements checklist

| Original requirement | Implementation |
|---|---|
| Open only an allowlisted target | [open_target.py](src/captcha_agent/tools/open_target.py), [allowlist.py](src/captcha_agent/allowlist.py) |
| Detect the widget | [detect_widget.py](src/captcha_agent/tools/detect_widget.py), [models.py](src/captcha_agent/models.py) |
| Solve with the appropriate tool | [pipeline.py](src/captcha_agent/pipeline.py), [click_checkbox.py](src/captcha_agent/tools/click_checkbox.py), [solve_slider.py](src/captcha_agent/tools/solve_slider.py), [solve_image_grid.py](src/captcha_agent/tools/solve_image_grid.py) |
| Verify independently | [verify_result.py](src/captcha_agent/tools/verify_result.py) |
| Produce evidence-backed reports | [browser.py](src/captcha_agent/browser.py), [evidence.py](src/captcha_agent/evidence.py), [report.py](src/captcha_agent/report.py) |
| Deterministic mode | [pipeline.py](src/captcha_agent/pipeline.py), [cli.py](src/captcha_agent/cli.py) |
| Agent mode | [loop.py](src/captcha_agent/agent/loop.py), [llm_client.py](src/captcha_agent/agent/llm_client.py), [prompts.py](src/captcha_agent/agent/prompts.py) |
| Shared tool schemas and registry | [tools/__init__.py](src/captcha_agent/tools/__init__.py) |
| Self-hosted fixture pages | [server.py](fixtures/server.py), [targets.yaml](config/targets.yaml) |

## Repeat the checks

```bash
cd /Users/irramfatima/Desktop/captch/captcha-agent
source .venv/bin/activate
python -m pytest -q
python scripts/measure_rates.py --widget all --runs 20
cat README.md | head -80
```
