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
- **Google Account** (for email SMTP)
- **LinkedIn Account** (for job scraping)
- **Mistral AI Account** (for embeddings)

### Setup (Choose Your Platform)

**Linux/macOS/WSL/BSD:**
```bash
git clone <repo>
cd agentic_job_finder
bash setup.sh
```

**Windows Command Prompt:**
```cmd
git clone <repo>
cd agentic_job_finder
setup.bat
```

**Windows PowerShell:**
```powershell
git clone <repo>
cd agentic_job_finder
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup.ps1
```

> **👉 See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed platform-specific instructions.**

---

## ⚙️ Configuration

### 1. Environment Variables
```bash
cp .env.example .env
nano .env  # Edit with your credentials
```

**Required:**
- `MISTRAL_API_KEY` - Get from [mistral.ai](https://mistral.ai)
- `JWT_SECRET_KEY` - Any random string
- `EMAIL_SENDER` - Your Gmail address
- `EMAIL_PASSWORD` - [Gmail app password](https://myaccount.google.com/apppasswords) (16 digits)

See [Configuration Reference](#-configuration-reference) for complete `.env` options.

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
DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db_name>
REDIS_URL=<redis-cluster-url-from-dashboard>
CELERY_BROKER_URL=<redis-cluster-url-from-dashboard>
QDRANT_URL=<qdrant-cluster-url-from-dashboard>
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

---

## 🔧 Configuration Reference

### Backend Environment Variables (`.env`)

| Variable | Purpose | Example |
|----------|---------|---------|
| `MISTRAL_API_KEY` | Embeddings API | Get from mistral.ai |
| `JWT_SECRET_KEY` | JWT secret | Any random string |
| `EMAIL_SENDER` | Gmail address | your-email@gmail.com |
| `EMAIL_PASSWORD` | Gmail app password | 16-digit app password |
| `REDIS_URL` | Redis connection | redis://redis:6379/0 |
| `QDRANT_URL` | Vector DB connection | http://qdrant:6333 |
| `DATABASE_URL` | PostgreSQL connection | postgresql+asyncpg://... |

**Other** (optional):
- `LANGCHAIN_API_KEY` - For LangChain tracing
- `LANGCHAIN_TRACING_V2` - Enable tracing (true/false)
- `DEVELOPMENT_MODE` - Enable dev features (true/false)

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

- ✅ AI-powered job discovery from multiple sources
- ✅ Semantic resume matching with vector embeddings
- ✅ Multi-factor relevance scoring
- ✅ Personalized AI-generated outreach messages
- ✅ Automated email digests
- ✅ Scheduled recurring pipeline runs
- ✅ Production-ready Docker architecture

---
