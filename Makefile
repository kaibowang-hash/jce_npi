.PHONY: start stop reset verify verify-dev-config verify-devcontainer verify-dev-environment frappe-init frappe-site-init frappe-runtime-verify frontend-install frontend-browser-install frontend-verify frontend-e2e frontend-visual
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
frappe-site-init:
	bash scripts/init-npi-site.sh
frappe-runtime-verify:
	bash scripts/verify-frappe-runtime.sh
frontend-install:
	npm --prefix frontend ci
frontend-browser-install:
	cd frontend && npx playwright install --with-deps chromium
frontend-verify:
	npm --prefix frontend run verify
frontend-e2e:
	npm --prefix frontend run test:e2e
frontend-visual:
	npm --prefix frontend run test:visual
