#!/bin/bash
# Cleanup script to remove unnecessary files and cache

echo "🧹 Cleaning up unnecessary files and caches..."

# Remove Python cache files
echo "Removing __pycache__ directories..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -name "*.pyd" -delete 2>/dev/null || true

# Remove old documentation files (now in main README.md)
echo "Removing outdated documentation..."
rm -f BROWSER_SESSION_AUTH_INTEGRATION.md 2>/dev/null || true
rm -f HEADLESS_BROWSER_INTEGRATION.md 2>/dev/null || true
rm -f OPERATIONS.md 2>/dev/null || true
rm -f qdrant_start.md 2>/dev/null || true
rm -f SCHEDULER_TEST.md 2>/dev/null || true
rm -f project_architecture.png 2>/dev/null || true

# Remove test files from root (they're in local_tests/)
echo "Consolidating tests to local_tests/..."
# Note: test_scheduler_reschedule.py is a new useful test - keep it in root
# Only remove old duplicates if they exist
[ -f test_job_discovery_agent.py ] && grep -q "^# Duplicate" test_job_discovery_agent.py && rm -f test_job_discovery_agent.py 2>/dev/null || true

# Optional: Remove mcp-server-qdrant if not needed (uncomment if unused)
# echo "Removing mcp-server-qdrant subproject..."
# rm -rf mcp-server-qdrant 2>/dev/null || true

echo "✅ Cleanup complete!"
echo ""
echo "Summary of removals:"
echo "  ✓ Python cache (__pycache__, *.pyc, *.pyd)"
echo "  ✓ Old documentation (now in README.md)"
echo "  ✓ Outdated guides (OPERATIONS, etc.)"
echo ""
echo "Kept (still useful):"
echo "  ✓ local_tests/ - Development tests"
echo "  ✓ test_scheduler_reschedule.py - Scheduler test utility"
echo "  ✓ clear_qdrant.py - Vector DB cleanup"
echo "  ✓ setup_login.py - Auth setup"
echo ""
echo "To completely clean git history of deleted files, run:"
echo "  git gc --aggressive"
echo "  git prune"
