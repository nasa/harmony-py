.PHONY: venv-setup pyenv-setup install install-examples clean examples lint test test-watch ci docs
.SILENT: virtualenv

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

install:
	python -m pip install --upgrade pip
	pip install -r requirements/core.txt -r requirements/dev.txt -r docs/requirements.txt

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

docs-notebook = examples/tutorial.ipynb
docs/user/notebook.html: $(docs-notebook)
	jupyter nbconvert --execute --to html --output notebook.html --output-dir docs/user $(docs-notebook)

docs: docs/user/notebook.html
	cd docs && $(MAKE) html
