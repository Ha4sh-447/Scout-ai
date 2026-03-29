#!/bin/bash
# Test database data persistence
set -e

echo "🧪 Testing database data persistence..."
echo ""

# Wait for database to be ready
echo "1️⃣  Waiting for database to be healthy..."
for i in {1..30}; do
    if docker ps | grep -q job_finder_db; then
        if docker exec job_finder_db pg_isready -U harsh -d job_agent >/dev/null 2>&1; then
            echo "   ✅ Database is ready"
            break
        fi
    fi
    echo "   ⏳ Attempt $i/30..."
    sleep 1
done

echo ""
echo "2️⃣  Creating test data..."
docker exec job_finder_db psql -U harsh -d job_agent -c "
CREATE TABLE IF NOT EXISTS persistence_test (
    id SERIAL PRIMARY KEY,
    test_data TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

INSERT INTO persistence_test (test_data) 
VALUES ('Test entry created at ' || NOW()::TEXT);
" && echo "   ✅ Test data inserted"

echo ""
echo "3️⃣  Reading test data (before restart)..."
BEFORE=$(docker exec job_finder_db psql -U harsh -d job_agent -t -c "SELECT COUNT(*) FROM persistence_test;" | tr -d ' ')
echo "   📊 Rows in table: $BEFORE"

echo ""
echo "4️⃣  Restarting database container..."
docker-compose restart db
echo "   ⏳ Waiting for restart..." && sleep 10

echo ""
echo "5️⃣  Reading test data (after restart)..."
AFTER=$(docker exec job_finder_db psql -U harsh -d job_agent -t -c "SELECT COUNT(*) FROM persistence_test;" | tr -d ' ')
echo "   📊 Rows in table: $AFTER"

echo ""
echo "════════════════════════════════════════════════════════════════"
if [ "$BEFORE" -eq "$AFTER" ] && [ "$AFTER" -gt 0 ]; then
    echo "✅ SUCCESS! Database data PERSISTS across restarts!"
    echo "   Before: $BEFORE rows"
    echo "   After:  $AFTER rows"
    echo "   Result: DATA IS SAFE! 🎉"
else
    echo "❌ FAILURE! Database data was lost!"
    echo "   Before: $BEFORE rows"
    echo "   After:  $AFTER rows"
    echo "   Problem: Data not persisting - check docker-compose.yml volumes"
fi
echo "════════════════════════════════════════════════════════════════"

echo ""
echo "🧹 Cleanup: Dropping test table..."
docker exec job_finder_db psql -U harsh -d job_agent -c "DROP TABLE IF EXISTS persistence_test;" && echo "✅ Done"
