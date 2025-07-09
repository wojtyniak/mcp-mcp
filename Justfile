# Development commands
dev:
    watchfiles --filter python "uv run main.py"

dev-http:
    watchfiles --filter python "uv run main.py --http"

run-http:
    uv run main.py --http

run-stdio:
    uv run main.py

# Testing
test:
    uv run pytest

test-unit:
    uv run pytest db/

test-integration:
    uv run pytest tests/

test-integration-github:
    MCP_MCP_TEST_GITHUB_INTEGRATION=1 uv run pytest tests/

test-all:
    MCP_MCP_TEST_GITHUB_INTEGRATION=1 uv run pytest

# Building
build: clean
    uv build

clean:
    rm -rf dist/ build/ *.egg-info/

# PyPI Publishing
publish-test: build
    @echo "Publishing to Test PyPI..."
    @if [ -z "${TWINE_PASSWORD}" ]; then echo "Error: TWINE_PASSWORD environment variable not set"; exit 1; fi
    TWINE_USERNAME=__token__ TWINE_REPOSITORY=testpypi uv run twine upload dist/*

publish-prod: build
    @echo "Publishing to Production PyPI..."
    @if [ -z "${TWINE_PASSWORD}" ]; then echo "Error: TWINE_PASSWORD environment variable not set"; exit 1; fi
    TWINE_USERNAME=__token__ uv run twine upload dist/*

# Utility commands
version:
    uv run main.py --version

update-readme:
    uv run python scripts/update_readme_shields.py

help:
    @just --list 
