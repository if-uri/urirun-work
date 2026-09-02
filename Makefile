.PHONY: install test doctor-build doctor-test doctor-health check

PY ?= python

install:
	$(PY) -m pip install -e .

doctor-build:
	$(PY) -m pip install --no-deps --no-build-isolation -e .

doctor-test:
	$(PY) -m pytest -q tests

doctor-health:
	$(PY) -c "import urirun_work"

test: doctor-test

check: test
