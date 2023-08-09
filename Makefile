.PHONY: install ruff mypy black isort typos test

all: ruff mypy black isort typos test

install:
	pip install -e .
	pip install -r requirements.txt -r dev-requirements.txt

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
