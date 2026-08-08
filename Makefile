# Convenience targets for the Nautobot Source of Truth lab.
# Run `make help` for the full list.

.DEFAULT_GOAL := help
.PHONY: help up down logs status seed validate lint backup intended compliance clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up: ## Start the Nautobot stack
	docker compose up -d

down: ## Stop the stack and remove containers
	docker compose down

logs: ## Follow the Nautobot logs
	docker compose logs -f nautobot

status: ## Show container health
	docker compose ps

seed: validate ## Validate then load the synthetic inventory into Nautobot
	python seed/seed_nautobot.py

validate: ## Run the seed and template validation suites
	python tests/validate_seed.py
	python tests/validate_templates.py

lint: ## Lint YAML, Python and Ansible
	yamllint -c .yamllint .
	ruff check .
	cd ansible && ansible-lint

backup: ## Back up running configurations from every device
	cd ansible && ansible-playbook playbooks/backup_configs.yml

intended: ## Render intended configurations from the Source of Truth
	cd ansible && ansible-playbook playbooks/generate_intended.yml

compliance: ## Compare running against intended and write a drift report
	cd ansible && ansible-playbook playbooks/check_compliance.yml

clean: ## Remove generated backups, intended configs and reports
	rm -rf backups intended reports
