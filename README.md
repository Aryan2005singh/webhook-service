# Webhook Service

A backend webhook ingestion and querying service built using FastAPI and SQLite, developed as part of a technical assessment.

---

## Overview

This service exposes a secure webhook endpoint that verifies incoming requests using HMAC-SHA256, ensures idempotent message processing, and stores data using SQLite.  
All configuration is managed via environment variables, and no external services are used.

---

## Features

- Secure webhook authentication using HMAC-SHA256
- Idempotent message handling using message_id
- SQLite-based data persistence
- Message retrieval with pagination and filters
- Aggregated statistics endpoint
- Health check endpoints for service monitoring
- Structured logging and metrics
- Docker-based setup

---

## Tech Stack

- Python
- FastAPI
- SQLite
- Pydantic
- Uvicorn
- Docker & Docker Compose

---

## Running the Service

### Prerequisites
- Docker
- Docker Compose

### Start the service
docker compose up -d --build

shell
Copy code

### View logs
docker compose logs -f

shell
Copy code

### Stop the service
docker compose down -v

yaml
Copy code

---

## Configuration

The service is configured using environment variables:

- `WEBHOOK_SECRET` – Secret used for HMAC signature verification (required)
- `DATABASE_URL` – SQLite database path (default: `/data/messages.db`)
- `LOG_LEVEL` – Logging level (default: `INFO`)

Environment variables can be provided via `.env` or `docker-compose.yml`.

---

## API Endpoints

### POST `/webhook`

Accepts incoming webhook requests.

- Verifies HMAC-SHA256 signature from `X-Signature` header
- Uses raw request body for signature verification
- Rejects invalid signatures with `401`
- Validates payload and returns `422` on validation errors
- Duplicate `message_id` values are ignored (idempotent behavior)
- Returns `200` on successful processing

---

### GET `/messages`

Retrieve stored messages with pagination and optional filters.

---

### GET `/stats`

Returns aggregated statistics such as total messages, unique senders, and message counts.

---

### GET `/health/live`

Liveness probe.  
Returns `200` when the service is running.

---

### GET `/health/ready`

Readiness probe.  
Returns `200` only when the database is accessible and `WEBHOOK_SECRET` is configured.

---

### GET `/metrics`

Exposes Prometheus-style metrics.

---

## Design Notes

- Webhook signatures are verified using HMAC-SHA256 over raw request body bytes.
- Idempotency is enforced using `message_id` as the primary key.
- SQLite is the only database used, as per assignment constraints.
- No external services or databases are integrated.

---

## Notes & Future Improvements (Out of Scope for This Assignment)

The following are conceptual improvements and are not implemented, as the assignment restricts usage to SQLite and no external services:

- Advanced authentication mechanisms
- Rate limiting
- Enhanced monitoring and alerting

---

## Setup Used

VS Code + ChatGPT + Claude (for debugging and clarification).
