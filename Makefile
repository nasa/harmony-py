.PHONY: install clean lint test ci docs

install:
	python -m pip install --upgrade pip
	pip install -r requirements/core.txt -r requirements/dev.txt

clean:
	coverage erase
	rm -rf htmlcov

lint:
	flake8 harmony --show-source --statistics

test:
	pytest --cov=harmony_py --cov-report=html --cov-branch tests

ci: lint test

docs:
	cd docs && $(MAKE) html
