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
	pytest

ci: lint test

docs:
	cd docs && $(MAKE) html
