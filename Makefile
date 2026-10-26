.PHONY: setup server test demo clean-port hitl

setup:
	./.venv/bin/pip install -e .

server:
	./.venv/bin/python -m fixtures.server --port 8765

test:
	./.venv/bin/python -m pytest -q

demo:
	./.venv/bin/python -m captcha_agent run --target local_checkbox --mode deterministic --headed
	./.venv/bin/python -m captcha_agent run --target local_slider --mode deterministic --headed
	./.venv/bin/python -m captcha_agent run --target local_none --mode deterministic --headed

clean-port:
	lsof -t -iTCP:8765 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true

hitl:
	@echo "HITL not implemented yet"
