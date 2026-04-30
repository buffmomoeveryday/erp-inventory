SHELL := /bin/sh

COMPOSE := docker compose
APP := web

.PHONY: help init build up down restart ps logs shell migrate makemigrations collectstatic check test config

help:
	@echo "Available targets:"
	@echo "  make init           # Create .env from .env.example if missing"
	@echo "  make build          # Build containers"
	@echo "  make up             # Start containers in background"
	@echo "  make down           # Stop and remove containers"
	@echo "  make restart        # Restart all containers"
	@echo "  make ps             # Show container status"
	@echo "  make logs           # Follow logs"
	@echo "  make shell          # Open shell inside web container"
	@echo "  make migrate        # Run Django migrations"
	@echo "  make makemigrations # Create Django migrations"
	@echo "  make collectstatic  # Run collectstatic"
	@echo "  make check          # Run django check"
	@echo "  make test           # Run test suite"
	@echo "  make config         # Validate docker compose config"

init:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; else echo ".env already exists"; fi

build: init
	$(COMPOSE) build

up: init
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

shell:
	$(COMPOSE) exec $(APP) sh

migrate:
	$(COMPOSE) exec $(APP) python manage.py migrate

makemigrations:
	$(COMPOSE) exec $(APP) python manage.py makemigrations

collectstatic:
	$(COMPOSE) exec $(APP) python manage.py collectstatic --noinput

check:
	$(COMPOSE) exec $(APP) python manage.py check

test:
	$(COMPOSE) exec $(APP) python manage.py test

config:
	$(COMPOSE) config
