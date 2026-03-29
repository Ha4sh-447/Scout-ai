#!/bin/bash
# Verify and fix database persistence issues

echo "🔍 Checking database persistence setup..."
echo ""

# Check if postgres_data volume exists
echo "1️⃣  Checking if postgres_data volume exists..."
docker volume ls | grep postgres_data
if [ $? -eq 0 ]; then
    echo "✅ Volume 'postgres_data' exists"
    echo ""
    echo "Volume details:"
    docker volume inspect postgres_data | head -20
else
    echo "❌ Volume 'postgres_data' NOT FOUND - This is the problem!"
    echo "   Data won't persist between restarts"
fi

echo ""
echo "2️⃣  Checking if postgres_data is mounted on db container..."
docker inspect job_finder_db 2>/dev/null | grep -A 10 "Mounts" || echo "Container not running"

echo ""
echo "3️⃣  Checking docker-compose.yml for volume definition..."
grep -A 2 "volumes:" docker-compose.yml | tail -5

echo ""
echo "4️⃣  Checking PostgreSQL data directory in container..."
docker exec job_finder_db ls -lh /var/lib/postgresql/data 2>/dev/null | head -10 || echo "Container not running or no access"

echo ""
echo "5️⃣  Database size:"
docker exec job_finder_db psql -U harsh -d job_agent -c "SELECT pg_size_pretty(pg_database_size('job_agent'));" 2>/dev/null || echo "Cannot connect to DB"

echo ""
echo "=================================================================================="
echo "📋 DIAGNOSIS COMPLETE"
echo "=================================================================================="
echo ""
echo "If volume NOT found, run these commands to fix:"
echo "  1. docker-compose down          # Don't use -v flag!"
echo "  2. docker volume create postgres_data"
echo "  3. docker-compose up -d"
echo ""
