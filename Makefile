.PHONY: install install-examples clean examples lint test test-watch ci docs

VERSION ?= $(shell git describe --tags | sed 's/-/\+/' | sed 's/-/\./g')
REPO ?= https://upload.pypi.org/legacy/
REPO_USER ?= __token__
REPO_PASS ?= unset

clean:
	coverage erase
	rm -rf htmlcov
	rm -rf build dist *.egg-info || true

clean-docs:
	cd docs && $(MAKE) clean

install:
	python -m pip install --upgrade pip
	pip install -r requirements/core.txt -r requirements/dev.txt -r requirements/docs.txt

install-examples: install
	pip install -r requirements/examples.txt

examples: install-examples
	jupyter-lab

lint:
	flake8 harmony --show-source --statistics

test:
	pytest --cov=harmony --cov-report=term --cov-report=html --cov-branch tests

test-watch:
	ptw -c -w

ci: lint test

docs-notebook = examples/tutorial.ipynb
docs/user/notebook.html: $(docs-notebook)
	jupyter nbconvert --execute --to html --output notebook.html --output-dir docs/user $(docs-notebook)

docs: docs/user/notebook.html
	cd docs && $(MAKE) html

version:
	sed -i.bak "s/__version__ .*/__version__ = \"$(VERSION)\"/" harmony/__init__.py && rm harmony/__init__.py.bak

build: clean version
	python -m pip install --upgrade --quiet setuptools wheel twine build
	python -m build

publish: build
	python -m twine check dist/*
	python -m twine upload --username "$(REPO_USER)" --password "$(REPO_PASS)" --repository-url "$(REPO)" dist/*
