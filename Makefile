.PHONY: dev test init migrate lint format prod
dev:        ## lance tout (back :8000, front :5173, mailhog :8025)
	docker compose up --build
migrate:
	docker compose run --rm backend python manage.py migrate
init:       ## base vide : organisation Digitalia + premier admin invité. make init EMAIL=... NAME="Prénom Nom"
	docker compose run --rm backend python manage.py init_orbit --email "$(EMAIL)" --name "$(NAME)"
test:
	docker compose run --rm backend pytest
	docker compose run --rm frontend sh -c "npm install --no-audit --no-fund && npm test -- --run"
lint:       ## ruff + mypy (back), eslint + prettier + tsc (front)
	docker compose run --rm backend sh -c "ruff check . && mypy ."
	docker compose run --rm frontend sh -c "npm run lint -- --max-warnings 0 && npm run format:check && npm run typecheck"
format:
	docker compose run --rm backend ruff check . --fix
	docker compose run --rm frontend npm run format
prod:       ## production (voir docs/08-deploiement.md)
	docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
