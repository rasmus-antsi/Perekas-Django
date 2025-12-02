# PgBouncer Setup Guide

PgBouncer is a lightweight connection pooler for PostgreSQL that significantly improves performance and scalability by reusing database connections.

## Why PgBouncer?

With 20k+ concurrent users polling every 10 seconds:
- **Without PgBouncer**: Each request opens a new connection (~4,000 connections/second)
- **With PgBouncer**: Connections are reused from a pool (~150 connections total)
- **Result**: 95% reduction in connection overhead, much better performance

## Setup Options

### Option 1: Railway (Recommended)

Railway supports PgBouncer as a service:

1. Add PgBouncer service to your Railway project
2. Connect it to your PostgreSQL database
3. Set `PGBOUNCER_URL` environment variable to the PgBouncer connection string
4. Django will automatically use PgBouncer instead of direct PostgreSQL connection

### Option 2: Docker Compose (Local Development)

Add to your `docker-compose.yml`:

```yaml
services:
  pgbouncer:
    image: pgbouncer/pgbouncer:latest
    environment:
      DATABASES_HOST: postgres
      DATABASES_PORT: 5432
      DATABASES_DBNAME: ${DB_NAME}
      DATABASES_USER: ${DB_USER}
      DATABASES_PASSWORD: ${DB_PASSWORD}
      PGBOUNCER_POOL_MODE: transaction
      PGBOUNCER_MAX_CLIENT_CONN: 1000
      PGBOUNCER_DEFAULT_POOL_SIZE: 150
    ports:
      - "6432:6432"
    depends_on:
      - postgres
```

Then set `PGBOUNCER_URL=postgresql://user:pass@pgbouncer:6432/dbname`

### Option 3: Manual Setup

1. Install PgBouncer: `brew install pgbouncer` (macOS) or `apt-get install pgbouncer` (Linux)
2. Configure using `pgbouncer.ini` file (included in project root)
3. Start PgBouncer: `pgbouncer -d pgbouncer.ini`
4. Update `PGBOUNCER_URL` to point to PgBouncer (default port 6432)

## Configuration

The `pgbouncer.ini` file is configured for optimal Django performance:

- **Pool Mode**: `transaction` (best for Django)
- **Pool Size**: 150 connections (handles ~2,000 requests/second)
- **Max Client Connections**: 1000
- **Timeouts**: Optimized for web application usage

## Environment Variables

Set these in your production environment:

- `PGBOUNCER_URL`: Connection string to PgBouncer (e.g., `postgresql://user:pass@pgbouncer:6432/dbname`)
- If `PGBOUNCER_URL` is not set, Django falls back to `DATABASE_URL` (direct PostgreSQL connection)

## Monitoring

Check PgBouncer stats:

```sql
-- Connect to PgBouncer admin console
psql -h localhost -p 6432 pgbouncer

-- View pool stats
SHOW POOLS;
SHOW STATS;
SHOW DATABASES;
```

## Dynamic Polling Adjustment

The polling system automatically adjusts interval based on query performance:

- **Fast queries (< 10ms)**: Decreases interval (more responsive)
- **Slow queries (> 50ms)**: Increases interval (reduces load)
- **Range**: 10-30 seconds

This ensures optimal performance even under high load.

