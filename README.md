# Webhook Service

A production-grade webhook ingestion and querying system built with FastAPI and SQLite.

## Features

- ✅ **HMAC-SHA256 Signature Verification** - Secure webhook authentication
- ✅ **Idempotent Message Storage** - Duplicate messages handled gracefully
- ✅ **Paginated Message Retrieval** - Efficient querying with filters
- ✅ **Real-time Statistics** - Aggregated metrics on messages and senders
- ✅ **Health Checks** - Liveness and readiness probes for orchestration
- ✅ **Structured JSON Logging** - Request tracking with correlation IDs
- ✅ **Prometheus Metrics** - Observability for monitoring systems
- ✅ **Docker Ready** - Containerized deployment with Docker Compose

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Make (optional, for convenience)

### Running the Service

```bash
# Start services
make up

# View logs
make logs

# Run tests
make test

# Stop services
make down
```

**Manual Docker Compose:**

```bash
docker compose up -d --build
docker compose logs -f api
docker compose down -v
```

### Configuration

Configure via environment variables (set in `docker-compose.yml` or `.env`):

- `WEBHOOK_SECRET` - HMAC secret for signature verification (required)
- `DATABASE_URL` - Path to SQLite database file (default: `/data/messages.db`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

## API Endpoints

### POST /webhook

Receive and store webhook messages.

**Headers:**
- `X-Signature` - HMAC-SHA256 hex signature of request body

**Request Body:**
```json
{
  "message_id": "msg-123",
  "from": "+1234567890",
  "to": "+0987654321",
  "ts": "2024-01-15T10:30:00.000Z",
  "text": "Hello World"
}
```

**Validation Rules:**
- `message_id` - Non-empty string
- `from` / `to` - E.164 format (`+` followed by digits)
- `ts` - ISO-8601 UTC with `Z` suffix
- `text` - Optional, max 4096 characters

**Responses:**
- `200` - Success (includes duplicates)
- `401` - Invalid or missing signature
- `422` - Validation error

**Idempotency:**
Duplicate `message_id` values are silently ignored (no error, returns 200).

---

### GET /messages

Retrieve messages with pagination and filters.

**Query Parameters:**
- `limit` - Results per page (default: 50, min: 1, max: 100)
- `offset` - Skip N results (default: 0, min: 0)
- `from` - Filter by sender (exact match)
- `since` - Filter by timestamp (ts >= since)
- `q` - Search text (case-insensitive substring)

**Response:**
```json
{
  "data": [
    {
      "message_id": "msg-123",
      "from": "+1234567890",
      "to": "+0987654321",
      "ts": "2024-01-15T10:30:00.000Z",
      "text": "Hello World",
      "created_at": "2024-01-15T10:30:01.123456Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0
}
```

**Ordering:**
Results are sorted by `ts ASC, message_id ASC`.

---

### GET /stats

Get aggregate statistics.

**Response:**
```json
{
  "total_messages": 1500,
  "senders_count": 42,
  "messages_per_sender": [
    {"from": "+1234567890", "count": 150},
    {"from": "+0987654321", "count": 120}
  ],
  "first_message_ts": "2024-01-01T00:00:00Z",
  "last_message_ts": "2024-01-15T23:59:59Z"
}
```

**Notes:**
- `messages_per_sender` returns top 10 senders sorted by count DESC
- Timestamps are `null` if no messages exist

---

### GET /health/live

Liveness probe - always returns `200` when service is running.

---

### GET /health/ready

Readiness probe - returns `200` only when:
- Database is accessible
- `WEBHOOK_SECRET` is configured

Returns `503` otherwise.

---

### GET /metrics

Prometheus-style metrics endpoint.

**Metrics:**
- `http_requests_total{method, path, status}` - Total HTTP requests
- `webhook_requests_total{result}` - Webhook processing outcomes

## Design Decisions

### HMAC Implementation

**Signature Generation:**
```python
import hmac
import hashlib

signature = hmac.new(
    secret.encode(),
    request_body_bytes,
    hashlib.sha256
).hexdigest()
```

**Verification:**
- Signature is computed from RAW request body bytes (before JSON parsing)
- Uses timing-safe comparison (`hmac.compare_digest`)
- Verification happens BEFORE database interaction
- Invalid signatures return 401 immediately (no DB writes)

**Security:**
- Prevents unauthorized message injection
- Protects against replay attacks (when combined with timestamp validation)
- HMAC-SHA256 provides cryptographic integrity

---

### Pagination Logic

**Implementation:**
1. Count total matching rows (respects filters)
2. Apply `LIMIT` and `OFFSET` to results
3. Return both data and total count

**Why this approach:**
- Client can calculate total pages: `ceil(total / limit)`
- Client knows if more results exist: `offset + len(data) < total`
- Filters affect total count (accurate pagination)

**SQL Strategy:**
```sql
-- Get total (respects filters)
SELECT COUNT(*) FROM messages WHERE <filters>

-- Get page (respects filters + ordering)
SELECT * FROM messages 
WHERE <filters>
ORDER BY ts ASC, message_id ASC
LIMIT ? OFFSET ?
```

---

### Stats Logic

**Aggregation Queries:**

1. **Total Messages:**
   ```sql
   SELECT COUNT(*) FROM messages
   ```

2. **Unique Senders:**
   ```sql
   SELECT COUNT(DISTINCT from_msisdn) FROM messages
   ```

3. **Top 10 Senders:**
   ```sql
   SELECT from_msisdn, COUNT(*) as count
   FROM messages
   GROUP BY from_msisdn
   ORDER BY count DESC
   LIMIT 10
   ```

4. **Timestamp Range:**
   ```sql
   SELECT MIN(ts) as first, MAX(ts) as last
   FROM messages
   ```

**Performance:**
- Indexes on `from_msisdn` and `ts` speed up aggregations
- Single database round-trip for all stats
- Returns `null` for timestamps when table is empty

---

### Database Schema

```sql
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX idx_from_msisdn ON messages(from_msisdn);
CREATE INDEX idx_ts ON messages(ts, message_id);
```

**Design Choices:**
- `message_id` as PRIMARY KEY enforces idempotency
- `INSERT OR IGNORE` handles duplicates gracefully
- Indexes optimize filtering and aggregations
- `created_at` tracks ingestion time (separate from message `ts`)

---

## Logging

Every request emits a structured JSON log line:

```json
{
  "ts": "2024-01-15T10:30:01.123Z",
  "level": "INFO",
  "request_id": "uuid-here",
  "method": "POST",
  "path": "/webhook",
  "status": 200,
  "latency_ms": 12.34,
  "message_id": "msg-123",
  "dup": false,
  "result": "success"
}
```

**Webhook-specific fields:**
- `message_id` - Message identifier
- `dup` - Boolean indicating duplicate
- `result` - Outcome: `success`, `duplicate`, `invalid_signature`, `validation_error`, `db_error`

**Benefits:**
- Easy parsing by log aggregators (ELK, Splunk, etc.)
- Request correlation via `request_id`
- Performance tracking via `latency_ms`

---

## Testing

**Run tests:**
```bash
make test           # Inside Docker container
make test-local     # Locally (requires deps)
```

**Test coverage:**
- ✅ HMAC signature validation (valid/invalid/missing)
- ✅ Payload validation (E.164, ISO-8601, text length)
- ✅ Idempotency (duplicate message_id)
- ✅ Pagination (limit, offset, ordering)
- ✅ Filters (from, since, q)
- ✅ Stats aggregation
- ✅ Health checks

---

## Development

**Local setup:**
```bash
# Install dependencies
make install-dev

# Run locally (without Docker)
export WEBHOOK_SECRET=your-secret
export DATABASE_URL=messages.db
uvicorn app.main:app --reload

# Format code
make format

# Lint code
make lint
```

---

## Setup Used

**Development Environment:**
- Editor: VSCode with Python extension
- AI Assistant: Claude (Anthropic) for code generation and review
- Testing: pytest with FastAPI TestClient
- Container: Docker + Docker Compose for deployment

**Key Tools:**
- FastAPI for high-performance async API
- Pydantic for data validation
- SQLite for zero-configuration persistence
- Uvicorn as ASGI server

---

## Production Considerations

**Scaling:**
- SQLite is single-writer; for high concurrency, migrate to PostgreSQL
- Add read replicas for /messages and /stats endpoints
- Use connection pooling for database access

**Security:**
- Rotate `WEBHOOK_SECRET` regularly
- Use HTTPS in production (TLS termination at load balancer)
- Implement rate limiting (e.g., 100 req/sec per IP)
- Add authentication for /messages and /stats if not public

**Observability:**
- Ship logs to centralized aggregator (Datadog, CloudWatch, etc.)
- Scrape /metrics endpoint with Prometheus
- Set up alerting on 5xx errors and high latency

**Backup:**
- Regular SQLite backups (e.g., `sqlite3 messages.db ".backup backup.db"`)
- Store backups in S3 or equivalent object storage

---

## License

This is a technical assessment project. No license specified.
