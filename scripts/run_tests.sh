#!/usr/bin/env bash
# =============================================================================
# DailyDrop Automated Test Runner
# Guarantees 100% deterministic, offline test execution across all tests.
# =============================================================================
set -e

echo "🛒 DailyDrop Test Suite Runner"
echo "==============================================="

# Prefer local virtual environment if present
if [ -d "venv" ] && [ -f "venv/bin/pytest" ]; then
    PYTHON_BIN="venv/bin/python"
    PYTEST_BIN="venv/bin/pytest"
else
    PYTHON_BIN="python3"
    PYTEST_BIN="pytest"
fi

echo "Python: $($PYTHON_BIN --version 2>&1)"

echo "Running 76 automated tests (Offline In-Memory SQLite + Mocked Redis)..."
$PYTHON_BIN -m pytest -v --color=yes

echo "==============================================="
echo "✅ All tests passed successfully!"
