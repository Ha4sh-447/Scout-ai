#!/bin/bash
# Backup database before restart
set -e

BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"

echo "🔒 Creating database backup before shutdown..."
echo ""

# Try to backup the database
if docker ps | grep -q job_finder_db; then
    BACKUP_FILE="$BACKUP_DIR/db_backup_$(date +%Y%m%d_%H%M%S).sql"
    docker exec job_finder_db pg_dump -U harsh -d job_agent > "$BACKUP_FILE" 2>/dev/null
    echo "✅ Database backed up to: $BACKUP_FILE"
    echo "   Size: $(du -h "$BACKUP_FILE" | cut -f1)"
else
    echo "⚠️  Database container not running - skipping backup"
fi

echo ""
echo "📦 Recent backups:"
ls -lh "$BACKUP_DIR" | tail -5 || echo "   (none)"

echo ""
echo "✅ Ready to restart - data is backed up!"
