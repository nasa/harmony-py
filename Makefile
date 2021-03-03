.PHONY: install install-examples clean examples lint test test-watch ci docs

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
