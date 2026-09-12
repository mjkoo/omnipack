# Fail instead of rewriting uv.lock when it is stale (keeps uv run check-only).
export UV_LOCKED := "1"

default:
    @just --list

# Install the locked environment
sync:
    uv sync --locked

# Format code
format:
    uv run ruff format

# Check formatting (no changes)
format-check:
    uv run ruff format --check

# Lint and apply safe fixes
lint:
    uv run ruff check --fix

# Lint (no changes)
lint-check:
    uv run ruff check

# Type check
typecheck:
    uv run ty check

# Verify uv.lock matches pyproject.toml
lock-check:
    uv lock --check

# Run tests with coverage
test:
    uv run pytest --cov

# Validate committed pack bytes and local configuration without network access
verify:
    uv run pack verify

# Run the write job's scripts' tests under CPython 3.12, the oldest runner
# python3 they must run on, without the project environment. The interpreter
# defaults to python312 from this flake's pinned nixpkgs; CI passes the
# runner's /usr/bin/python3.
check-py312 python="":
    #!/usr/bin/env bash
    set -euo pipefail
    unset UV_LOCKED
    python={{ quote(python) }}
    if [ -z "$python" ]; then
        python="$(nix build --inputs-from . --no-link --print-out-paths nixpkgs#python312)/bin/python3.12"
    fi
    uv run --no-project --python "$python" --with pytest \
        pytest tests/test_nightly_write.py tests/test_source_proposal.py \
        tests/test_workflow_support.py

# Lint the workflows with actionlint and zizmor
lint-actions:
    actionlint
    zizmor --persona pedantic .github/workflows

# Check documentation links without making network requests
check-links:
    lychee --offline docs/ README.md

# Run every flake check
flake-check:
    nix flake check

# Format nix files
nix-fmt:
    nix fmt

# Check nix formatting without writing (what CI runs)
nix-fmt-check:
    nix fmt -- --ci

# Everything CI runs
check-all: lock-check format-check lint-check typecheck test verify check-py312 lint-actions check-links nix-fmt-check flake-check
