# 🤖 Agentic Job Finder

An intelligent job discovery platform powered by AI agents that finds, matches, ranks, and helps you reach out to relevant job opportunities personalized to your profile.

**Status**: ✅ Production Ready | **Tech Stack**: Python, FastAPI, LangChain, PostgreSQL, Redis, Qdrant, React/Next.js

---

## 🎯 What It Does

- 🔍 **Discovers** jobs from LinkedIn, Indeed, Reddit, and custom URLs
- 🎯 **Matches** jobs to your resume using semantic search (vector embeddings)
- ⭐ **Ranks** jobs by relevance, recency, and source quality
- 💬 **Generates** personalized outreach messages (email & LinkedIn)
- 📧 **Notifies** you via email with job digests
- ⏰ **Schedules** recurring pipeline runs automatically

---

## 🚀 Quick Start

### Prerequisites
- **Python** 3.9+, **Docker**, **Git**
- **Google Account** (for email SMTP & optional OAuth)
- **LinkedIn Account** (for job scraping)
- **Mistral AI Account** (required for embeddings + LLM fallback)
- **Groq Account** (optional but recommended for better fallback coverage and faster LLM functionality)
- **Node.js 18+** (for frontend development)

### Setup (All Platforms)

```bash
git clone <repo>
python setup.py
```

> Works on Linux, macOS, and Windows — no bash or PowerShell required.
> **👉 See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed setup instructions.**

---

## ⚙️ Configuration

### 1. Environment Variables
```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

**Required:**
- `MISTRAL_API_KEY` - Get from [mistral.ai](https://mistral.ai) (Embeddings & Backup LLM)
- `JWT_SECRET_KEY` - Any random string (Backend auth)
- `AUTH_SECRET` - Random string for NextAuth (`openssl rand -base64 32`)
- `EMAIL_SENDER` - Your Gmail address
- `EMAIL_PASSWORD` - [Gmail app password](https://myaccount.google.com/apppasswords)
- `DATABASE_URL` - PostgreSQL connection string
- `QDRANT_URL` - Qdrant endpoint (local Docker or cloud)

**Optional but recommended:**
- `GROQ_API_KEY` - Get from [groq.com](https://groq.com) (optional but recommended for better fallbacks and faster LLM functionality)
- `QDRANT_API_KEY` - Required only when your Qdrant deployment has auth enabled (Qdrant Cloud / secured cluster). Optional for local unsecured Qdrant.

See [Configuration Reference](#-configuration-reference) for the complete list of system environment variables.

### 2. Start Services
```bash
docker-compose up -d
docker-compose ps  # Verify all services are running
```

### 3. LinkedIn Authentication
To personalize job scraping, authenticate with LinkedIn:

```bash
# Get your User ID (create account via frontend first)
# Then run:
python scripts/auth_helper.py --user-id YOUR_USER_ID --platforms linkedin

# Browser opens → log in → script saves session automatically
```

---

## ▶️ Running the Application

### Step 1: Start Backend Services (Docker)
```bash
docker-compose up
```

This starts everything:
- PostgreSQL database
- Redis cache
- Qdrant vector DB
- FastAPI server
- Celery worker

Watch for all services to be "UP" before proceeding.

### Step 2: Start Frontend (New Terminal)
```bash
cd frontend
npm run dev
```

### Access Application
- 🌐 **Frontend**: http://localhost:3000
- 📚 **API Docs**: http://localhost:8001/docs
- ✅ **Health Check**: `curl http://localhost:8001/health`

---

## 🔧 Local Development (No Docker)

Use this mode only if you want everything running locally.

### 1) Start required infrastructure

Required:
- PostgreSQL (port 5432)

Optional local services (skip if using managed clusters):
- Redis (port 6379)
- Qdrant (port 6333)

Example start commands:
```bash
# Linux (systemd)
sudo systemctl start postgresql
sudo systemctl start redis

# macOS (Homebrew)
brew services start postgresql
brew services start redis

# Qdrant (local binary)
qdrant
```

### 2) Set local environment variables in `.env`
```env
# Core API keys
MISTRAL_API_KEY=<mistral-api-key>
GROQ_API_KEY=<groq-api-key>                    # optional but recommended
QDRANT_API_KEY=<qdrant-api-key>

# Auth / app secrets
JWT_SECRET_KEY=<jwt-secret>
AUTH_SECRET=<nextauth-secret>

GOOGLE_CLIENT_ID=<google-oauth-client-id>
GOOGLE_CLIENT_SECRET=<google-oauth-client-secret>
LANGCHAIN_API_KEY=<langchain-api-key>

# Infrastructure
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db_name>
REDIS_URL=<redis-cluster-url-from-dashboard>
CELERY_BROKER_URL=<redis-cluster-url-from-dashboard>
QDRANT_URL=<qdrant-cluster-url-from-dashboard>

# Notifications
EMAIL_SENDER=<sender-email>
EMAIL_PASSWORD=<email-app-password>
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
```

Examples:
```env
# Local services
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
QDRANT_URL=http://localhost:6333

# Managed services (from provider dashboards)
REDIS_URL=rediss://default:<password>@<host>:<port>
CELERY_BROKER_URL=rediss://default:<password>@<host>:<port>
QDRANT_URL=https://<cluster-id>.<region>.cloud.qdrant.io
QDRANT_API_KEY=<qdrant-api-key>
```

### 3) Run backend and frontend

**Terminal 1: API**
```bash
source .venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001
```

**Terminal 2: Celery Worker**
```bash
source .venv/bin/activate
celery -A workers.worker worker --loglevel=info
```

**Terminal 3: Frontend**
```bash
cd frontend && npm run dev
```

---

## 📊 First Pipeline Run

1. **Create account** → Visit http://localhost:3000 → Sign up
2. **Upload resume** → Dashboard → My Resumes → Upload PDF/DOCX
3. **Configure search** → Dashboard → Preferences → Set keywords, location, experience
4. **Add job URLs** → Dashboard → Search URLs → Add LinkedIn/Indeed job search URLs
5. **Trigger pipeline** → Dashboard → Pipeline History → Click "Trigger Pipeline"
6. **Check results** → View matched jobs in dashboard or check your email

---

## 🧠 How It Works

```
Job Discovery → Resume Matching → Ranking → Messaging → Email Notification
    ↓              ↓                  ↓         ↓            ↓
Scrape jobs   Vector embeddings   Weight by    Generate   Send HTML
from URLs     + semantic search   relevance    outreach   digest
```

**Key Steps:**
1. **Discovery**: Scrapes LinkedIn, Indeed, Reddit, custom URLs
2. **Matching**: Uses vector embeddings (Mistral) to find relevant jobs
3. **Ranking**: Scores by match (85%), recency (7.5%), source quality (7.5%)
4. **Messaging**: AI generates personalized connection messages
5. **Notification**: Sends email digest with jobs and suggested messages

### Qdrant Auth and User Isolation

- `QDRANT_API_KEY` is optional in docs because local Docker Qdrant commonly runs without API auth.
- For Qdrant Cloud or any secured deployment, set `QDRANT_API_KEY`.
- Resume vectors are isolated per user in payload metadata and query filters:
    - Chunk vectors are stored with `user_id` and `resume_id`.
    - Full-resume vectors are stored with `user_id` and `resume_id`.
    - Retrieval always applies a `must` filter on `user_id` (and often `resume_id`).
- During resume upload, old vectors for the same `user_id + resume_id` are deleted before upsert, so each resume version remains consistent.

### Qdrant Access Architecture (Native vs MCP)

- This project has two Qdrant access paths on purpose:
- Native app path (used by the pipeline):
    `resume/pipeline.py` and `agents/resume_matching/agent.py` call `core/qdrant_mcp.py`, which uses `AsyncQdrantClient` directly against `QDRANT_URL`.
- MCP tool path (used by MCP-compatible clients):
    the `qdrant-mcp` service in `docker-compose.yml` runs `mcp-server-qdrant` on port `8000` and exposes MCP tools like `qdrant-find` and `qdrant-store`.

Why keep both:
- Native path keeps internal pipeline operations fast and tightly controlled.
- MCP path enables external MCP clients/agents to query or store semantic memory in the same Qdrant backend.
- Do not remove `mcp-server-qdrant` during Docker optimizations if MCP tooling is part of your workflow.

---

## 🔧 Configuration Reference

### Backend Environment Variables (`.env`)

| Variable | Purpose | Example |
|----------|---------|---------|
| `MISTRAL_API_KEY` | Embeddings & LLM | Get from mistral.ai |
| `GROQ_API_KEY` | Fast LLM Provider (optional but recommended) | Get from groq.com |
| `JWT_SECRET_KEY` | Backend Signatures | Any random string |
| `AUTH_SECRET` | NextAuth Encryption | `openssl rand -base64 32` |
| `EMAIL_SENDER` | SMTP Sender | your-email@gmail.com |
| `EMAIL_PASSWORD` | SMTP Password | 16-digit app password |
| `REDIS_URL` | Task Queue Broker | redis://redis:6379/0 |
| `QDRANT_URL` | Vector DB connection | http://qdrant:6333 |
| `QDRANT_API_KEY` | Qdrant auth token (required on secured/cloud Qdrant) | Optional for local; required for cloud |
| `DATABASE_URL` | Postgres Connection | postgresql+asyncpg://... |

**Advanced Configuration (Optional):**

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_USER_DAILY_LIMIT` | Max AI calls per user/day | `30` |
| `EMAIL_SMTP_HOST` | SMTP Server Host | `smtp.gmail.com` |
| `EMAIL_SMTP_PORT` | SMTP Server Port | `587` |
| `FRONTEND_URL` | CORS allow-origin | `http://localhost:3000` |
| `GOOGLE_CLIENT_ID` | Google OAuth ID | (Optional) |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Secret | (Optional) |
| `LANGCHAIN_API_KEY` | LLM Observability | (Optional) |
| `LANGCHAIN_TRACING_V2` | Enable LC Tracing | `false` |
| `DEVELOPMENT_MODE` | Detailed Debug Logs | `true` |

### Frontend Environment Variables (`.env` in `/frontend`)

| Variable | Purpose | Example |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | API endpoint | http://localhost:8001 |
| `NEXTAUTH_URL` | Auth base URL | http://localhost:3000 |
| `AUTH_SECRET` | Auth encryption | Generate with: `openssl rand -base64 32` |

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| **Docker services fail to start** | Check logs: `docker-compose logs` <br> Ensure ports 5432, 6379, 6333 are free |
| **LinkedIn auth timeout** | Run from project root: `cd /path/to/agentic_job_finder` <br> Increase timeout: `--timeout 120` |
| **Emails not sending** | Verify Gmail 2FA enabled <br> Check app password is correct (no spaces) |
| **Jobs not matching** | Confirm resume uploaded and processed <br> Check Qdrant: `curl http://localhost:6333/health` |
| **Pipeline slow/stuck** | Check Celery worker: `docker-compose logs job_finder_celery` <br> Monitor resources: `docker stats` |

---

## 📚 Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed platform-specific setup
- **[SETUP.md](SETUP.md)** - Alternative setup documentation
- **API Docs** - http://localhost:8001/docs (when running)

---

## ✨ Features

- ✅ **Smart LLM Routing**: Distributed load-balancing across Groq and Mistral providers, with provider auto-enablement based on available keys.
- ✅ **Circuit Breaker**: Auto-healing rate-limit protection for all AI operations.
- ✅ **Per-User AI Quotas**: Enforced daily limits to manage capacity and costs.
- ✅ **Response Caching**: Efficient AI usage via SHA256-keyed caching.
- ✅ **AI-powered job discovery** from multiple sources (LinkedIn, Indeed, etc.).
- ✅ **Semantic resume matching** with vector embeddings and chunk-vote winner selection across resumes.
- ✅ **Platform-aware URL query rewriting**: updates existing search params (for example `roles`, `keywords`) instead of blindly appending new ones.
- ✅ **Generic scraper hardening**: popup-aware extraction and stronger filtering for navigation/ad links on generic portals.
- ✅ **Seen-job loop safety in workers**: async Redis access uses per-call clients to avoid event-loop reuse issues.
- ✅ **Multi-factor relevance scoring** (Match, Recency, Quality).
- ✅ **Personalized AI outreach** message generation.
- ✅ **Automated email digests** & recurring scheduled runs.
- ✅ **Automatic job cleanup**: Daily deletion of results >7 days old.
- ✅ **Unified setup system**: Single `python setup.py` for all OS platforms.
- ✅ **Production-ready** Docker-orchestrated architecture.

---
