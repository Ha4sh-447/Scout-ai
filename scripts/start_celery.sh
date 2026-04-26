#!/bin/bash

set -e

if [ "${PLAYWRIGHT_INSTALL_ON_STARTUP:-true}" = "true" ]; then
    echo "[STARTUP] Ensuring Playwright Chromium is installed..."
    python -m playwright install chromium
fi

echo "[STARTUP] Starting Celery worker..."
exec celery -A workers.worker worker --loglevel=info --concurrency=4
