# Workspaces: add --all-packages to the sync and build targets.
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

# Audit dependencies for known vulnerabilities
audit:
    uv audit

# Run tests with coverage
test:
    uv run pytest --cov

# Build sdist and wheel (not `dist/`: that holds the rendered pack output)
build:
    uv build --no-sources --out-dir build/python-dist

# Lint the workflows with actionlint and zizmor
lint-actions:
    actionlint
    zizmor --persona regular .github/workflows

# Run every flake check
flake-check:
    nix flake check

# Format nix files
nix-fmt:
    nix fmt

# Check nix formatting without writing (what CI runs)
nix-fmt-check:
    nix fmt -- --ci

# Build the image and load it into the local docker daemon
docker-load:
    $(nix build .#docker --no-link --print-out-paths) | docker image load

# Everything CI runs
check-all: lock-check format-check lint-check typecheck audit build test lint-actions nix-fmt-check flake-check
