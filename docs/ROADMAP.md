# CAPTCHA Agent Roadmap

## Scope and compliance boundary

This repository is a local, self-hosted test harness. The allowed targets are the
fixtures in `config/targets.yaml`; the agent must never navigate to an
unapproved host or attempt to defeat a third-party CAPTCHA.

The attached image-grid challenge resembles a provider CAPTCHA. For this project,
implement it only as a local mock where a human selects the correct tiles. Do not
add image classification, answer prediction, stealth behavior, proxy rotation,
fingerprint spoofing, or instructions for bypassing a real provider challenge.
The compliant design is human-in-the-loop: the browser pauses, the user completes
the challenge, and the agent verifies the resulting success state before moving
to the next local stage.

## Requirement interpretation

| Requirement | Implementation decision | Acceptance test |
|---|---|---|
| Checkbox stage | Local `role=checkbox` fixture; manual click | Status becomes `verified` and `window.__captcha_solved` is true |
| Slider stage | Local randomized puzzle; manual drag in workflow mode | Piece is within tolerance and status becomes `verified` |
| Image-grid stage | New local mock; manual tile selection and submit | Correct local tile set produces `verified` |
| No-CAPTCHA stage | Existing normal login fixture | Workflow reaches the login page without solving a CAPTCHA |
| Sequential workflow | One same-origin workflow page with an iframe and state machine | Stage N cannot load stage N+1 before verification |
| Agent mode | Tool calls are allowlisted and verification is independent | Model claims never override `verify_result` |
| Evidence | Screenshot, JSONL events, trace, and report per run | Every transition has timestamped evidence |

## Target directory plan

```text
captcha-agent/
├── config/
│   ├── targets.yaml              # local allowlist and success rules
│   └── settings.yaml             # timeouts and run limits
├── fixtures/
│   ├── index.html                # fixture home page
│   ├── workflow.html             # manual sequential workflow
│   ├── checkbox.html             # local checkbox fixture
│   ├── slider.html               # local slider fixture
│   ├── image_grid.html           # planned local manual tile fixture
│   ├── none.html                 # no-CAPTCHA fixture
│   ├── assets/                   # generated local images only
│   └── server.py                 # loopback-only aiohttp server
├── src/captcha_agent/
│   ├── agent/                    # LLM protocol, prompts, bounded loop
│   ├── tools/                    # typed allowlisted browser tools
│   ├── vision/                   # slider geometry only; no image CAPTCHA solver
│   ├── browser.py                # Playwright lifecycle and tracing
│   ├── config.py                 # Pydantic/YAML validation
│   ├── allowlist.py              # scheme/host/port enforcement
│   ├── pipeline.py               # deterministic orchestration
│   └── report.py                 # JSON and Markdown evidence reports
├── tests/
│   ├── test_workflow.py          # sequential/manual-gate behavior
│   ├── test_image_grid.py        # local mock correctness
│   ├── test_allowlist.py
│   ├── test_tools.py
│   └── test_slider_gap.py
└── docs/ROADMAP.md               # this plan and LLM prompts
```

## Implementation phases

### Phase A — local image-grid fixture

Create `fixtures/image_grid.html` with a deterministic local board, a prompt,
keyboard-accessible selectable tiles, a submit button, and a visible status.
Store the expected tile IDs in fixture data for tests only. The browser workflow
may observe the success state, but must not read the expected answer to solve it.
Add `local_image_grid` to `config/targets.yaml` with a selector-based success
rule. Add tests for correct selection, incorrect selection, reset, and keyboard
accessibility.

### Phase B — manual gate in the workflow

Add the image-grid stage after the slider in `fixtures/workflow.html`:

```text
checkbox → slider → image-grid (manual) → no-CAPTCHA login
```

The workflow should only poll the current iframe's success flag/text. It must not
click the checkbox, drag the slider, select tiles, or submit the image grid.
On failure, keep the user on the current stage and display a useful status. On
success, capture a screenshot and append a transition event before navigation.

### Phase C — typed agent support

Add a `complete_image_grid` tool only if its behavior is explicitly a human
handoff (pause, show instructions, wait for a verified state). Do not expose a
tool that guesses tiles. Keep `verify_result` as the source of truth.

### Phase D — evidence and regression coverage

Record `stage_started`, `manual_verification_required`, `stage_verified`, and
`stage_failed` events. Add an e2e test that completes the local stages with test
actions, asserting that advancing before verification is impossible. Keep real
provider URLs out of the allowlist and test data.

## Prompts to give an LLM

### Architecture prompt

```text
You are modifying a Python 3.11+ Playwright project named captcha_agent.
Inspect the existing repository before editing. Preserve the src layout,
Pydantic models, YAML configuration, typed TOOL_REGISTRY, allowlist enforcement,
evidence recorder, and deterministic pipeline. The only allowed browser targets
are the loopback fixtures in config/targets.yaml. Do not add support for real
third-party CAPTCHA providers and do not infer or predict image-grid answers.
First describe the files you will change, then implement the smallest safe patch,
then run the focused tests and report failures with their causes.
```

### Local image-grid fixture prompt

```text
Implement a self-hosted fixtures/image_grid.html test page. It must be a local
mock only, use a fixed test board with accessible buttons/checkboxes, show a
prompt such as “Select all tiles containing bicycles”, and require the human to
select tiles and press Verify. Keep the expected tile IDs in test-only fixture
data, never expose them through the agent API, and set status=verified plus a
success flag only for the correct selection. Add a Pydantic/YAML target and
pytest tests for correct, incorrect, reset, and keyboard behavior. Do not use
OCR, computer vision, image classification, or any real provider endpoint.
```

### Sequential workflow prompt

```text
Update fixtures/workflow.html so the user manually completes checkbox, slider,
and local image-grid stages in that order, followed by none.html. The page must
never click, drag, or select on behalf of the user. Observe only the current
fixture's verified state, capture a transition event, and load the next iframe
only after independent verification succeeds. Add an e2e test proving that the
next stage is blocked before verification and opens afterward.
```

### Agent guardrail prompt

```text
Review the agent loop for safety. Unknown tools, invalid Pydantic arguments,
navigation outside the configured scheme/host/port, and model claims of success
must be rejected. For any image-grid challenge, stop for human completion and
wait for verify_result; never select tiles or infer an answer. Maintain a maximum
step count, wall-clock timeout, three-error circuit breaker, screenshots, and
JSONL events. Add focused tests for each guardrail.
```

### Test-and-review prompt

```text
Run the project with the configured virtual environment. Execute the focused
workflow tests, then the full pytest suite. Check that every configured URL is
loopback-only, every dependency is declared in pyproject.toml and requirements.txt,
Playwright Chromium is installed, and no test requires an Anthropic API key.
Summarize changed files, test counts, known limitations, and exact commands for
a fresh macOS setup.
```

## Dependency compatibility

The current dependency set is sufficient for the existing local fixtures and
workflow:

- `playwright`: browser automation and trace capture
- `pydantic`, `pyyaml`: validated models and configuration
- `typer`, `rich`: CLI and terminal output
- `python-dotenv`: optional environment loading
- `aiohttp`: loopback fixture server
- `opencv-python-headless`, `numpy`, `pillow`: slider fixture generation and
  slider geometry tests only
- `anthropic`: optional agent provider; local deterministic/mock mode must work
  without an API key
- `pytest`, `pytest-asyncio`: development and browser tests

The image-grid mock needs no new dependency. Avoid adding a computer-vision or
OCR package for it; that would conflict with the human-verification boundary.

## macOS setup commands

```bash
cd /Users/irramfatima/Desktop/captch/captcha-agent

# Confirm Python 3.11 or newer.
python3 --version

# Create and activate the project environment.
python3 -m venv .venv
source .venv/bin/activate

# Install runtime and development dependencies.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Install the browser used by Playwright.
python -m playwright install chromium

# Rebuild local slider assets.
python fixtures/make_assets.py
```

## Run commands

Start the loopback fixture server in Terminal 1:

```bash
cd /Users/irramfatima/Desktop/captch/captcha-agent
source .venv/bin/activate
python fixtures/server.py --port 8765
```

Open the manual sequential workflow in a browser:

```text
http://127.0.0.1:8765/workflow.html
```

Useful direct pages:

```text
http://127.0.0.1:8765/checkbox.html
http://127.0.0.1:8765/slider.html
http://127.0.0.1:8765/none.html
```

Run checks in Terminal 2:

```bash
cd /Users/irramfatima/Desktop/captch/captcha-agent
source .venv/bin/activate
PYTHONPATH=src python -m captcha_agent list-targets
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python scripts/smoke_browser.py
```

Run local mode without an Anthropic key:

```bash
PYTHONPATH=src python -m captcha_agent run-all --mode deterministic
PYTHONPATH=src python -m captcha_agent run-all --mode agent --mock
```

Use Anthropic only when explicitly configured:

```bash
export ANTHROPIC_API_KEY="your-key"
export LLM_MODEL="your-approved-model"
PYTHONPATH=src python -m captcha_agent run --target local_checkbox --mode agent
```

## Definition of done

- The root page links to the workflow and each direct fixture.
- The workflow never auto-solves a manual stage.
- The image-grid fixture is local, deterministic, accessible, and tested.
- The agent pauses for human completion instead of guessing image answers.
- All navigation is allowlisted and loopback-only.
- `pytest` passes without an API key.
- Reports include screenshots, events, trace links, verification evidence, and a
  clear PASS/FAIL/SKIPPED verdict.
