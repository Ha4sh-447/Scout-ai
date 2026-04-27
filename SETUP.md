# Agentic Job Finder - Setup Guide

## Quick Start

### 1. Automated Setup (Recommended)
Run the universal setup script (works on Linux, macOS, and Windows) for a polished, interactive experience:

```bash
python setup.py
```

This script will:
- ✓ **Polished CLI**: Experience a modern, centered command-line interface.
- ✓ Check prerequisites (Python, pip, Docker, Node/npm)
- ✓ Create `.env` from `.env.example` if missing
- ✓ Setup Python virtual environment
- ✓ Install Python dependencies
- ✓ Install Playwright browsers
- ✓ Create required data directories
- ✓ Setup frontend dependencies
- ✓ Start Docker containers (optional)
- ✓ Run database migrations (optional)

### 2. Manual Setup

If you prefer manual setup or need to troubleshoot:

#### Prerequisites
- Python 3.11+
- PostgreSQL (or Docker)
- Redis (or Docker)
- Node.js & npm (for frontend)
- Docker & Docker Compose (optional but recommended)

#### Step-by-step

1. **Clone and setup environment**
   ```bash
   git clone https://github.com/Ha4sh-447/Scout-ai.git
   cd Scout-ai
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Setup frontend**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

5. **Create data directories**
   ```bash
   mkdir -p data/resumes
   ```

6. **Start Docker services** (recommended)
   ```bash
   docker-compose up -d
   ```

   This starts:
   - PostgreSQL database
   - Redis (for Celery)
   - Qdrant vector DB
   - Celery worker
   - MCP Qdrant Server

7. **Run database migrations**
   ```bash
   cd db/migrations
   PYTHONPATH=../.. alembic upgrade head
   cd ../..
   ```

8. **Run preflight checks**
   ```bash
   python scripts/preflight.py
   ```

## Environment Variables

Required variables in `.env`:

```env
# API Keys
MISTRAL_API_KEY=your_key_here
GROQ_API_KEY=your_key_here (optional but recommended, for better fallback and faster LLM functionality)
QDRANT_API_KEY=your_key_here (optional for local Qdrant, required for cloud/secured Qdrant)

# Database
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db_name>
DB_USER=<user>
DB_PASSWORD=your_password
DB_NAME=<db_name>

# Qdrant Vector DB
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your_key (optional)

# Redis (for Celery)
CELERY_BROKER_URL=redis://localhost:6379/0

# Email (Required for notifications)
EMAIL_SENDER=sender@gmail.com
EMAIL_PASSWORD=your_google_app_password_here
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_RECIPIENT=recipient@gmail.com
```

### Why QDRANT_API_KEY Is Optional in Some Places

- Local Docker Qdrant usually runs without authentication, so `QDRANT_API_KEY` can be omitted.
- Qdrant Cloud or any secured Qdrant deployment requires `QDRANT_API_KEY`.
- `QDRANT_URL` is still required so the app knows where to connect.

### How User Resume Data Is Isolated in Qdrant

- Every stored vector includes payload metadata with `user_id` and `resume_id`.
- Resume retrieval queries filter by `user_id` (and optionally `resume_id`), so users do not query each other's vectors.
- On resume re-upload, vectors for the same `user_id + resume_id` are cleared before upserting the new version.

### Recent Pipeline/Matching Updates

- Semantic resume matching now uses full job context and chunk-vote winner selection (not only top single chunk score).
- Generic scraping was hardened with popup-aware extraction and stronger ad/navigation filtering.
- URL query injection is now dynamic and updates existing search-intent params when present (instead of blindly appending `q`).
- Seen-job Redis tracking in workers is loop-safe to avoid `Event loop is closed` failures across Celery tasks.

## Docker Services

The docker-compose.yml includes:

### PostgreSQL
- Container: `job_finder_db`
- Port: `5432`
- Volume: `postgres_data`
- Healthcheck: Enabled

### Redis
- Container: `job_finder_redis`
- Port: `6379`
- Purpose: Celery broker

### Qdrant
- Container: `qdrant`
- Ports: `6333`, `6334`
- Volume: `qdrant_data`
- Purpose: Vector database for embeddings

### Celery Worker
- Container: `job_finder_celery`
- Purpose: Background job processing
- Concurrency: 4 workers
- Depends on: Redis, PostgreSQL, Qdrant

### MCP Qdrant Server
- Container: `qdrant-mcp`
- Port: `8000`
- Purpose: MCP protocol server for Qdrant

## Running the Application

### Start Backend Services
```bash
# Terminal 1: Activate environment and start backend
source .venv/bin/activate
python api/main.py
# Backend runs on http://localhost:8001
```

### Start Frontend
```bash
# Terminal 2: Start frontend dev server
cd frontend
npm run dev
# Frontend runs on http://localhost:3000
```

### Start Celery Worker
```bash
# Terminal 3 (if not using Docker): Start Celery worker
source .venv/bin/activate
celery -A workers.worker worker --loglevel=info
```

## Troubleshooting

### Database Connection Issues

If migrations fail with "cannot connect to database":

1. Verify PostgreSQL is running:
   ```bash
   docker-compose ps
   # Should show: job_finder_db is running
   ```

2. Check DATABASE_URL:
   ```bash
   grep DATABASE_URL .env
   ```

3. Test connection:
   ```bash
   psql -h localhost -U <user> -d <db_name>
   ```

### Alembic Migration Issues

If migrations fail:

```bash
# Check migration status
cd db/migrations
PYTHONPATH=../.. alembic current

# View migration history
PYTHONPATH=../.. alembic history

# Reset and re-run (destructive)
psql -h localhost -U <user> -d <db_name> -c "DELETE FROM alembic_version;"
PYTHONPATH=../.. alembic upgrade head
```

### Docker Issues

If containers won't start:

```bash
# Check logs
docker-compose logs -f job_finder_db

# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Port Already in Use

If ports are already taken:

```bash
# Change ports in docker-compose.yml
# OR kill existing processes
lsof -i :5432  # Find process using port 5432
kill -9 <PID>
```

## Development Commands

### Create Database Migration
```bash
cd db/migrations
PYTHONPATH=../.. alembic revision --autogenerate -m "description"
cd ../..
```

### Run Tests
```bash
pytest local_tests/
```

## Notes

### Automatic Job Cleanup
Scraped job results older than **7 days** are automatically deleted from the `job_results` table on every application startup and once every 24 hours thereafter. This keeps the database lean. Jobs that were already emailed/delivered to users remain in their inbox.

### Scheduler Tests
```bash
python local_tests/test_job_discovery_agent.py
python local_tests/test_matching_pipeline.py
python local_tests/test_full_pipeline.py
```

## Architecture Overview

```
┌─────────────────┐
│   Frontend      │ (Next.js/React)
│   :3000         │
└────────┬────────┘
         │ HTTP
┌─────────────────┐
│   FastAPI       │ ← API Gateway
│   :8001         │
└─┬─────────────┬─┘
  │             │
  │ Celery      │ Redis ← Task Queue
  │ :8000       │ :6379
  │             │
  └──────┬──────┘
         │
    ┌────┴─────────────────┐
    │                      │
┌───▼───────┐      ┌──────▼─────┐
│ PostgreSQL│      │   Qdrant    │
│ :5432     │      │   :6333     │
│ (DB)      │      │ (Embeddings)│
└───────────┘      └─────────────┘
```

## Next Steps

1. **Set up authentication**: Run `scripts/setup_login.py`
2. **Add your resume**: Upload PDF via frontend
3. **Configure job search**: Set queries, location, experience level
4. **Enable scheduler**: Toggle scheduling for automated runs
5. **Check job matches**: View ranked results in dashboard

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review preflight checks: `python scripts/preflight.py`
- Check migrations: `cd db/migrations && PYTHONPATH=../.. alembic history`

