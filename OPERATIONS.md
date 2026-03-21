# Operations Guide: Monitoring & Management

This document explains how to monitor, debug, and manage the background workers and API in deployment.

## 1. Monitoring Processes (Which is running?)

### A. Real-time Dashboard (Flower)

**Flower** is the gold standard for monitoring Celery.

- **Start**: `celery -A workers.worker flower --port=5555`
- **View**: `http://localhost:5555`
- **What it shows**:
  - **Active Tasks**: What's running *now*.
  - **Processed/Failed**: History of all tasks.
  - **Broker Status**: Is the queue full?

### B. Command Line (CLI)

Use these to check the health from the terminal:

```bash
# See active tasks across all nodes (what the worker is doing right NOW)
celery -A workers.worker inspect active

# See reserved tasks (jobs waiting for their turn in the worker's pool)
celery -A workers.worker inspect reserved

# Check worker health
celery -A workers.worker status
```

---

## 2. Managing the Queue (What's in Redis?)

The **Redis Broker** holds the messages (tasks) that are waiting for a worker.

- **View Queue Length** (using `redis-cli` if available):

  ```bash
  redis-cli -u YOUR_REDIS_URL llen celery
  ```

- **Purge Everything** (Empty the whole queue):

  ```bash
  celery -A workers.worker purge -f
  ```

---

## 3. Database State (The "Log")

The `pipeline_runs` table is the **official history**.

- **Pending**: Task is queued but hasn't started or is waiting for a worker.
- **Running**: Worker has picked it up and is actively processing.
- **Done/Failed**: Terminal states.

If a task is **Running** in DB but **Empty** in `celery inspect active`, it means the worker likely crashed or was killed while processing.

---

## 4. Disaster Recovery (The Clean-up)

If you have "ghost" tasks or hit connection limits:

1. **Kill ALL processes**: `pkill -f "celery|api.main|python -m api.main"`
2. **Reset System**: `python scripts/system_reset.py` (Clears queue & DB history)
3. **Start fresh**:
   - Start API
   - Start Worker
