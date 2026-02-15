.PHONY: venv install install-test test test-v run run-once clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

venv:
	python3 -m venv $(VENV)

install: venv
	$(PIP) install -e .

install-test: venv
	$(PIP) install -e ".[test]"

test: install-test
	$(PYTEST)

test-v: install-test
	$(PYTEST) -v

run: install
	$(PYTHON) -m stock_checker

run-once: install
	$(PYTHON) -m stock_checker --once

clean:
	rm -rf $(VENV) .pytest_cache *.egg-info stock_checker.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
