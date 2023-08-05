.PHONY: install ruff mypy black isort typos test

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

typos:
	typos --format brief

test:
	pytest

fmt:
	ruff cicada test --fix
	isort .
	black cicada test

clean:
	rm -rf .mypy_cache .ruff_cache dist build cicada/build cicada/dist
