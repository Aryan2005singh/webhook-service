.PHONY: up down logs test clean build help

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

up: ## Start services (build and run in detached mode)
	docker compose up -d --build

down: ## Stop services and remove volumes
	docker compose down -v

logs: ## Tail logs from API service
	docker compose logs -f api

test: ## Run tests inside container
	docker compose exec api pytest tests/ -v

test-local: ## Run tests locally (requires deps installed)
	pytest tests/ -v

build: ## Build Docker image
	docker compose build

clean: ## Clean up containers, volumes, and images
	docker compose down -v --rmi local

restart: ## Restart services
	docker compose restart

ps: ## Show running containers
	docker compose ps

shell: ## Open shell in API container
	docker compose exec api /bin/bash

install-dev: ## Install development dependencies locally
	pip install -r requirements.txt
	pip install pytest httpx

format: ## Format code with black
	black app/ tests/

lint: ## Lint code with flake8
	flake8 app/ tests/ --max-line-length=100
