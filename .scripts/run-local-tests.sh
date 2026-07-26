#!/usr/bin/env bash
set -euo pipefail

# Local development test runner script
PROJECT_NAME="esports-manager"

cd "$(dirname "$0")/.."

echo "Running local development tests..."

# Navigate to project root and determine the project path
if [ -f "pyproject.toml" ] && [ -d "src/esports_manager" ]; then
    PROJECT_ROOT="."
    echo "Found project at: $(pwd)"
elif [ -d "esports_manager" ]; then
    PROJECT_ROOT="esports_manager"
else
    echo "Error: Could not find esports-manager project structure"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d ".venv" ] || [ ! -f ".venv/bin/python" ]; then
    echo "Setting up development environment..."
    python -m pip install --upgrade pip
    pip install uv
    uv sync --group dev
fi

# Set up paths
export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"

# Initialize test database if needed
if [ ! -f "$PROJECT_ROOT/data/test_environment.db" ]; then
    echo "Initializing test database..."
    cd "$PROJECT_ROOT"
    uv run python -c "
from esports_manager.db import _ensure_tables
import sqlite3
conn = sqlite3.connect('data/test_environment.db')
_ensure_tables(conn)
print('Test database initialized')
"
fi

# Run unit tests
echo "Running unit tests..."
uv run pytest tests/ -v --tb=short --cov="$PROJECT_ROOT/esports_manager" --cov-report=term-missing

# Run linting
echo "Running lint checks..."
uv run ruff check "$PROJECT_ROOT/esports_manager" "tests/"
uv run ruff format --check "$PROJECT_ROOT/esports_manager" "tests/"

# Create test summary
echo "\n" > test_summary.md
echo "# $PROJECT_NAME Test Summary" >> test_summary.md
echo "" >> test_summary.md
echo "Generated: $(date)" >> test_summary.md
echo "" >> test_summary.md
echo "## Test Results" >> test_summary.md
echo "" >> test_summary.md
echo "- Unit Tests: Completed" >> test_summary.md
echo "- Linting: Completed" >> test_summary.md
echo "- Coverage: Available in CI/reports" >> test_summary.md

echo "Test suite completed successfully!"
