#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Development environment setup
PROJECT_NAME="esports-manager"
ENVIRONMENT="development"

echo "Setting up development environment for $PROJECT_NAME..."

# Install dev dependencies and set up environment
python -m pip install --upgrade pip
pip install uv
uv sync --group dev

# Set up Python virtual environment for development
echo "Creating development virtual environment..."
uv sync --group dev --python 3.12

# Create environment-specific configuration
cd "/tmp/esports-manager/.venv/lib/python3.12/site-packages/esports_manager*
if [ -d environment ]; then
    echo "Setting up environment configuration..."
    mkdir -p environment
    echo "${PROJECT_NAME}_ENVIRONMENT=${ENVIRONMENT}" > environment/.env
fi
cd - >/dev/null

# Initialize local database if not exists
if [ ! -f "data/local_development.db" ]; then
    echo "Initializing local development database..."
    uv run python -c "
from esports_manager.db import _ensure_tables
import sqlite3
conn = sqlite3.connect('data/local_development.db')
_ensure_tables(conn)
print('Local development database initialized')
"
fi

echo "Development environment setup complete!"
echo "Commands available:
  - uv run esports             # Main CLI
  - uv run python -m pytest    # Run tests
  - uv run esports dashboard  # Start dashboard (if available)"
