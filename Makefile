.PHONY: up down build migrate seed pull-model logs shell

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f api worker

# Run Alembic migrations inside the api container
migrate:
	docker compose exec api alembic upgrade head

# Seed initial topics into the database
seed:
	docker compose exec api python -m app.scripts.seed

# Pull the default Ollama model (qwen2.5:7b)
pull-model:
	docker compose exec ollama ollama pull qwen2.5:7b

# Pull a lighter model for low-VRAM machines
pull-model-small:
	docker compose exec ollama ollama pull qwen2.5:3b

# Open a Python shell in the api container
shell:
	docker compose exec api python

# Run tests
test:
	docker compose exec api pytest tests/ -v

# Trigger trend discovery manually
discover-trends:
	docker compose exec api python -m app.scripts.run_discovery

# Generate a video for a given topic ID
# Usage: make generate TOPIC_ID=1
generate:
	docker compose exec api python -m app.scripts.generate_video --topic-id $(TOPIC_ID)

# Show Celery task queue status
queue-status:
	docker compose exec api celery -A app.core.celery_app inspect active

clean-storage:
	@echo "Removing generated audio, images, videos (keeps directory structure)"
	find ./storage -type f -not -name ".gitkeep" -delete
