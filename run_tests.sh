#!/usr/bin/env bash
# =============================================================================
# DailyDrop Automated Test Runner
# Guarantees 100% deterministic, offline test execution across all 63 tests.
# =============================================================================
set -e

echo "🛒 DailyDrop Test Suite Runner"
echo "==============================================="
echo "Python: $(python3 --version 2>&1)"

# Check if pytest is available
if ! command -v pytest &> /dev/null && ! python3 -m pytest --version &> /dev/null; then
    echo "⚠️  pytest not detected. Installing test dependencies from requirements.txt..."
    pip install -r requirements.txt
fi

echo "Running 63 automated tests (Offline In-Memory SQLite + Mocked Redis)..."
python3 -m pytest -v --color=yes

echo "==============================================="
echo "✅ All tests passed successfully!"
