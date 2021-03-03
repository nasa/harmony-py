.PHONY: virtualenv install install-examples clean examples lint test test-watch ci docs
.SILENT: virtualenv

virtualenv:
	if ! type xxxpyenv > /dev/null; \
	then \
	    echo "\nUnable to create virtualenv: pyenv not found. Please install pyenv, pyenv-virtualenv, and Python 3.8.5."; \
	    exit; \
	else \
	    pyenv virtualenv 3.8.5 harmony-py; \
	    pyenv local harmony-py; \
	    pyenv activate harmony-py; \
	fi

install:
	python -m pip install --upgrade pip
	pip install -r requirements/core.txt -r requirements/dev.txt

install-examples: install
	pip install -r requirements/examples.txt

clean:
	coverage erase
	rm -rf htmlcov

examples: install-examples
	jupyter-lab

lint:
	flake8 harmony --show-source --statistics

test:
	pytest --cov=harmony --cov-report=term --cov-report=html --cov-branch tests

test-watch:
	ptw -c -w

ci: lint test

docs:
	cd docs && $(MAKE) html
