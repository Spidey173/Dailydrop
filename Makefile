.PHONY: run worker migrate seed test lint format

PYTHON ?= python3

run:
	$(PYTHON) app.py

worker:
	$(PYTHON) worker.py

migrate:
	$(PYTHON) -m migrations.runner

seed:
	$(PYTHON) seed.py

test:
	pytest -v

lint:
	ruff check .

format:
	black .
	ruff check --fix .
