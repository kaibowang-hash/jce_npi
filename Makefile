.PHONY: start stop reset verify verify-dev-config verify-devcontainer verify-dev-environment frappe-init
start:
	docker compose up -d
stop:
	docker compose stop
reset:
	@test "$${CONFIRM_RESET}" = "YES" || (echo "Set CONFIRM_RESET=YES"; exit 2)
	docker compose down --volumes
verify:
	bash scripts/verify.sh
verify-dev-config:
	bash scripts/verify-dev-config.sh
verify-devcontainer:
	python scripts/verify_devcontainer.py
verify-dev-environment:
	bash scripts/verify-dev-environment.sh
frappe-init:
	bash scripts/init-frappe-bench.sh
