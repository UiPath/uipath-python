set quiet

default: lint format

lint:
    ruff check .
    python scripts/lint_httpx_client.py

format:
    ruff format --check .

validate: lint format

update-agents-md: validate
    python scripts/update_agents_md.py

build: update-agents-md
    uv build

install:
    uv sync --all-extras

# Test the custom linter
test-lint-httpx:
    python scripts/test_httpx_linter.py
