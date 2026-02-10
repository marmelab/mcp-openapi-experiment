SHELL := /bin/bash

.PHONY: install start clean


ERASE_VENV ?= 0

install:
	@if ! command -v uv >/dev/null 2>&1; then \
		echo "Installing uv..."; \
		curl -LsSf https://astral.sh/uv/install.sh | sh; \
	fi
	@if [ -d .venv ] && [ "$(ERASE_VENV)" = "1" ]; then \
		echo "Removing existing .venv..."; \
		rm -rf .venv; \
	fi
	@UV_CMD=$$(command -v uv 2>/dev/null || echo $$HOME/.local/bin/uv); \
	$$UV_CMD venv --allow-existing .venv
	@UV_CMD=$$(command -v uv 2>/dev/null || echo $$HOME/.local/bin/uv); \
	$$UV_CMD pip install --python .venv/bin/python fastmcp httpx

clean:
	@rm -rf .venv

start: install
	@.venv/bin/python server.py
