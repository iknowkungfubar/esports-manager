#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Add PROJECT_NAME variable for local customization
PROJECT_NAME="esports-manager"

echo "Setting up local CI environment for $PROJECT_NAME..."

# Install dependencies with uv
python -m pip install --upgrade pip
pip install uv
uv sync --group dev

# Run linting
echo "Running linting..."
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/

# Run tests
echo "Running tests..."
uv run pytest tests/ --cov=src/esports_manager --cov-report=term-missing

echo "CI setup complete!"
