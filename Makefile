.PHONY: venv-setup pyenv-setup install install-examples clean examples lint test test-watch ci docs
.SILENT: virtualenv

VERSION ?= $(shell git describe --tags | sed 's/-/\+/' | sed 's/-/\./g')
REPO ?= https://upload.pypi.org/legacy/
REPO_USER ?= __token__
REPO_PASS ?= unset

venv-setup:
	python -m venv .venv

pyenv-setup:
	if ! type pyenv > /dev/null; \
	then \
	    echo "\nUnable to create virtualenv: pyenv not found. Please install pyenv & pyenv-virtualenv."; \
	    echo "  See:"; \
	    echo "    https://github.com/pyenv/pyenv"; \
	    echo "    https://github.com/pyenv/pyenv-virtualenv"; \
	    exit; \
	else \
	    pyenv install 3.9.1; \
	    pyenv virtualenv 3.9.1 harmony-py; \
	    pyenv local harmony-py; \
	fi

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

build: clean
	sed -i.bak "s/__version__ .*/__version__ = \"$(VERSION)\"/" harmony/__init__.py && rm harmony/__init__.py.bak
	python -m pip install --upgrade --quiet setuptools wheel twine
	python setup.py --quiet sdist bdist_wheel

publish: build
	python -m twine check dist/*
	python -m twine upload --username "$(REPO_USER)" --password "$(REPO_PASS)" --repository-url "$(REPO)" dist/*
