set quiet

default: lint format

lint:
    ruff check .

format:
    ruff format --check .

build:
    uv build

install:
    uv sync --all-extras
