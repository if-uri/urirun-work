.PHONY: install test check

install:
	python -m pip install -e .

test:
	python -m pytest -q tests

check: test

