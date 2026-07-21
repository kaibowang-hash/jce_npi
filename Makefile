.PHONY: start stop reset verify
start:
	docker compose up -d
stop:
	docker compose stop
reset:
	@test "$${CONFIRM_RESET}" = "YES" || (echo "Set CONFIRM_RESET=YES"; exit 2)
	docker compose down --volumes
verify:
	bash scripts/verify.sh
