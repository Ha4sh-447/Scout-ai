#!/bin/bash
# Wait for PostgreSQL to be ready and run migrations

set -e

# Extract database connection info from DATABASE_URL or environment variables
if [ -z "$DATABASE_URL" ]; then
    DB_HOST="${DB_HOST:-db}"
    DB_PORT="${DB_PORT:-5432}"
    DB_USER="${DB_USER:-harsh}"
    DB_NAME="${DB_NAME:-job_agent}"
else
    # Parse DATABASE_URL (postgresql+asyncpg://user:pass@host:port/db)
    DB_HOST=$(echo "$DATABASE_URL" | sed -E 's/.*@([^:]+):.*/\1/')
    DB_PORT=$(echo "$DATABASE_URL" | sed -E 's/.*@[^:]+:([^/]+).*/\1/')
    DB_USER=$(echo "$DATABASE_URL" | sed -E 's/.*\/\/([^:]+):.*/\1/')
    DB_NAME=$(echo "$DATABASE_URL" | sed -E 's/.*\/([^?]+).*/\1/')
fi

echo "[STARTUP] Database connection info:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  User: $DB_USER"
echo "  Database: $DB_NAME"

# Wait for PostgreSQL to be ready
echo "[STARTUP] Waiting for PostgreSQL to be ready at $DB_HOST:$DB_PORT..."
max_attempts=30
attempt=1

while [ $attempt -le $max_attempts ]; do
    if pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > /dev/null 2>&1; then
        echo "[STARTUP] ✓ PostgreSQL is ready!"
        break
    fi
    
    echo "[STARTUP] Attempt $attempt/$max_attempts: PostgreSQL not ready yet, waiting..."
    sleep 2
    attempt=$((attempt + 1))
done

if [ $attempt -gt $max_attempts ]; then
    echo "[STARTUP] ✗ FAILED: PostgreSQL did not become ready after $max_attempts attempts"
    exit 1
fi

# Run Alembic migrations
echo "[STARTUP] Running database migrations..."
cd /app/db/migrations

if alembic upgrade head; then
    echo "[STARTUP] ✓ Migrations completed successfully"
else
    echo "[STARTUP] ✗ FAILED: Alembic migrations failed"
    exit 1
fi

cd /app
echo "[STARTUP] ============ Database Setup Complete ============"

# Start the Uvicorn server
echo "[STARTUP] Starting Uvicorn server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8001
