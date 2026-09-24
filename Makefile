.PHONY: check

check:
	python -m unittest discover -s tests -v
	npm --prefix frontend run build
	docker compose config --quiet
	terraform -chdir=infra/terraform fmt -check -recursive
	terraform -chdir=infra/terraform validate
