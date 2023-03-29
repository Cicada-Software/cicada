.PHONY: install ruff mypy black isort test

all: ruff mypy black isort test

install:
	pip install .
	pip install -r requirements.txt
	pip install -r dev-requirements.txt

install-local:
	pip install -e .

ruff:
	ruff cicada test

mypy:
	mypy -p cicada
	mypy -p test

black:
	black cicada test --check --diff

isort:
	isort . --diff --check

test:
	pytest

fmt:
	ruff cicada test --fix
	isort .
	black cicada test
