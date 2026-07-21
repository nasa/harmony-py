.PHONY: install install-examples clean examples lint test test-watch ci docs

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
	pip install .
	pip install .[dev,docs]

install-minimum:
	python -m pip install --upgrade pip
	pip install -r requirements-min.txt
	pip install .[dev,docs] --constraint requirements-min.txt

install-examples: install
	pip install .[examples]

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

build: clean
	python -m pip install --upgrade --quiet setuptools wheel twine build
	python -m build

publish: build
	python -m twine check dist/*
	python -m twine upload --username "$(REPO_USER)" --password "$(REPO_PASS)" --repository-url "$(REPO)" dist/*
