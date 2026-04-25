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

set +e
ALEMBIC_OUTPUT=$(alembic upgrade head 2>&1)
ALEMBIC_STATUS=$?
set -e

echo "$ALEMBIC_OUTPUT"

if [ $ALEMBIC_STATUS -eq 0 ]; then
    echo "[STARTUP] ✓ Migrations completed successfully"
else
    if echo "$ALEMBIC_OUTPUT" | grep -q "Can't locate revision identified by"; then
        if [ "${ALLOW_ALEMBIC_STAMP_REPAIR:-false}" = "true" ]; then
            HEAD_REV=$(alembic heads | awk 'NR==1{print $1}')
            if [ -z "$HEAD_REV" ]; then
                echo "[STARTUP] ✗ FAILED: Could not resolve Alembic head revision"
                exit 1
            fi

            echo "[STARTUP] ⚠ Unknown Alembic revision detected in database."
            echo "[STARTUP] ⚠ Repair enabled: forcing alembic_version to head revision: $HEAD_REV"

            if [ -n "$DATABASE_URL" ]; then
                PSQL_URL=$(python - <<'PY'
import os

url = os.environ.get("DATABASE_URL", "")
url = url.replace("postgresql+asyncpg://", "postgresql://")
url = url.replace("postgres+asyncpg://", "postgres://")
print(url)
PY
)
                psql "$PSQL_URL" <<SQL
CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL);
TRUNCATE TABLE alembic_version;
INSERT INTO alembic_version(version_num) VALUES ('$HEAD_REV');
SQL
            else
                if [ -z "$DB_PASSWORD" ]; then
                    echo "[STARTUP] ✗ FAILED: DB_PASSWORD is required for Alembic repair mode when DATABASE_URL is not set"
                    exit 1
                fi

                export PGPASSWORD="$DB_PASSWORD"
                psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" <<SQL
CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL);
TRUNCATE TABLE alembic_version;
INSERT INTO alembic_version(version_num) VALUES ('$HEAD_REV');
SQL
            fi

            alembic upgrade head
            echo "[STARTUP] ✓ Migrations completed after revision repair"
        else
            echo "[STARTUP] ✗ FAILED: Alembic revision in DB is unknown to this codebase"
            echo "[STARTUP]   Set ALLOW_ALEMBIC_STAMP_REPAIR=true to auto-stamp to current head"
            echo "[STARTUP]   Or reset volume / manually update alembic_version table"
            exit 1
        fi
    else
        echo "[STARTUP] ✗ FAILED: Alembic migrations failed"
        exit 1
    fi
fi

cd /app
echo "[STARTUP] ============ Database Setup Complete ============"

# Start the Uvicorn server
echo "[STARTUP] Starting Uvicorn server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8001
