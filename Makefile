.PHONY: install clean lint test ci docs

install:
	python -m pip install --upgrade pip
	pip install -r requirements/core.txt -r requirements/dev.txt

clean:
	coverage erase
	rm -rf htmlcov

lint:
	flake8 harmony_py --show-source --statistics

test:
	nosetests --with-coverage --cover-html --cover-branches --cover-package=harmony_py --cover-erase --nocapture --nologcapture

ci: lint test

docs:
	cd docs && $(MAKE) html
