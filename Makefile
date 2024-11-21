build:
	poetry build
	pip install dist/*.tar.gz
	poetry version --short > ip2email/_version
	pyinstaller --clean \
		--onefile \
		--add-data ./ip2email/_version:. \
		--workpath ./pyinstaller \
		--name ip2email \
		--hidden-import ip2email \
		ip2email/main.py

create-dev:
	pre-commit install
	rm -rf env
	python3.10 -m venv env
	( \
		. env/bin/activate; \
		pip install -r requirements.txt; \
		poetry install; \
		deactivate; \
	)
