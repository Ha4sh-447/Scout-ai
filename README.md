# Agentic Job Finder

An AI-powered multi-agent job discovery and matching platform that automatically finds, parses, matches, ranks, and notifies users about relevant job opportunities from multiple sources. Combines web scraping, semantic matching, and AI reasoning to deliver personalized job recommendations.

## 📋 Table of Contents

- [Features](#-features)
- [Quick Start](#-quick-start)
- [Project Overview](#-project-overview)
- [Architecture](#-architecture)
- [Technology Stack](#-technology-stack)
- [Directory Structure](#-directory-structure)
- [Setup Instructions](#-setup-instructions)
- [Running the Application](#-running-the-application)
- [API Documentation](#-api-documentation)
- [Database Schema](#-database-schema)
- [Configuration](#-configuration)
- [Development & Testing](#-development--testing)

## ✨ Features

### Core Capabilities

- **🔍 Multi-Source Job Discovery**
  - LinkedIn job scraping (with authentication)
  - Wellfound (Y Combinator) startup jobs
  - Generic URL scraping for custom job boards
  - Reddit job posting detection
  - Intelligent pagination and link extraction

- **🧠 Semantic Job Matching**
  - Resume-to-job semantic similarity using embeddings
  - FastEmbed for local embedding generation (no external calls)
  - Vector search in Qdrant database
  - Configurable match thresholds

- **⭐ Intelligent Ranking**
  - Multi-factor scoring:
    - Match score (80% weight): Semantic similarity
    - Recency (10% weight): Job posting freshness
    - Source quality (7.5% weight): Platform reliability
    - Recruiter type (2.5% weight): Direct vs agency
  - Duplicate detection using content hashing

- **📧 Email Notifications**
  - SMTP integration for reliable email delivery
  - HTML-formatted job digest emails
  - Match score explanations in every email
  - Scheduled batch notifications

- **📅 Automatic Scheduling**
  - Per-pipeline scheduling with configurable intervals (1-24 hours)
  - APScheduler for reliable task scheduling
  - Automatic recovery after application restarts
  - Execution tracking and history

- **🔐 Secure Authentication**
  - NextAuth.js with email/password credentials
  - JWT token-based API authentication
  - Browser session persistence for authenticated scraping
  - OAuth integration support (Google, etc.)

- **📊 Dashboard & Monitoring**
  - Real-time pipeline execution status
  - Job match results with scores and filtering
  - Resume management interface
  - Search configuration and scheduling controls
  - Pipeline history with execution metrics

- **🌐 Resume Management**
  - PDF resume upload and parsing
  - Multi-resume support per user
  - Resume text chunking and embedding
  - Automatic resume-to-job matching

### Advanced Features

- **🤖 Multi-Agent LangGraph Pipeline**
  - Job Discovery Agent: Scrapes and parses job listings
  - Resume Matching Agent: Semantic matching with embedding reranking
  - Ranking Agent: Composite scoring and prioritization
  - Messaging Agent: AI-generated outreach drafts (for future features)
  - Notification Agent: Email formatting and sending

- **🔄 Deduplication & Data Cleaning**
  - Content-based job deduplication using SHA256 hashing
  - Company name sanitization (removes "Inc", "LLC", etc.)
  - Duplicate link detection and consolidation

- **⚙️ Background Job Processing**
  - Celery task queue for long-running operations
  - Redis message broker for task distribution
  - Configurable concurrency and worker pools
  - Task retry logic and error handling

- **📈 Detailed Execution Metrics**
  - Jobs discovered count per pipeline run
  - Jobs matched count (after resume evaluation)
  - Jobs ranked count (final results)
  - Execution duration tracking
  - Error logging and debugging info

## 🚀 Quick Start

```bash
# 1. Clone and setup environment
git clone <repo>
cd agentic_job_finder
cp .env.example .env  # Configure your environment

# 2. Start services
docker-compose up -d  # Start PostgreSQL, Redis, Qdrant

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python run_migration.py
python run_migration_resumes.py

# 5. Start backend
python scripts/start_backend.py

# 6. Start Celery worker (in separate terminal)
celery -A workers.worker.celery_app worker -l info --concurrency=1

# 7. Start frontend (in another terminal)
cd frontend && npm install && npm run dev

# 8. Open http://localhost:3000
```

## 📊 Project Overview

The Agentic Job Finder is a sophisticated multi-agent system that:

1. **Discovers** job listings from multiple platforms (LinkedIn, Wellfound, Reddit, custom URLs)
2. **Parses** job postings to extract structured information (title, company, skills, requirements)
3. **Deduplicates** similar jobs and sanitizes company names
4. **Matches** jobs against user resumes using vector embeddings (semantic similarity)
5. **Ranks** matched jobs based on relevance scores and recency
6. **Notifies** users about top matches via email
7. **Manages** pipeline execution history with scheduling and execution tracking
8. **Persists** browser sessions for authenticated scraping

## 🏛️ Architecture

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                        │
│  - Dashboard: View jobs, resumes, pipeline history               │
│  - Settings: Configure search, resume uploads                    │
│  - Auth: NextAuth.js with credentials/OAuth                      │
└────────────────────┬────────────────────────────────────────────┘
                     │ HTTP/REST API
┌────────────────────▼────────────────────────────────────────────┐
│                   Backend (FastAPI)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Auth Router  │  │ Jobs Router   │  │ Scrapers     │            │
│  │ (login)      │  │ (CRUD jobs)   │  │ (authenticate)           │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Users Router │  │ Pipeline API │  │ Resume API   │            │
│  │ (profiles)   │  │ (trigger/list)   │ (upload)     │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼──┐  ┌──────▼───┐  ┌────▼──────┐
│ Celery   │  │ APScheduler   │  │ Database │
│ Worker   │  │ (interval)    │  │ (PostgreSQL)
└────┬─────┘  └──────┬───────┘  └────┬─────┘
     │               │               │
     └───────────────┼───────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
┌───────▼────────┐ ┌─┴──────────┐ ┌──┴──────────┐
│ AI Agents      │ │ Qdrant     │ │ Redis Queue │
│ (LangGraph)    │ │ (Embeddings) │ │ (Tasks)    │
└────────────────┘ └────────────┘ └────────────┘
```

### Data Flow

```
USER TRIGGER
    ↓
[API: POST /jobs/trigger]
    ↓
[Celery Task: run_pipeline_task]
    ↓
┌─────────────────────────────────────┐
│ Stage 1: Job Discovery              │
│ - Fetch URLs from user settings     │
│ - Load job listings using Playwright│
│ - Extract job links and descriptions│
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│ Stage 2: Job Parsing & Dedup        │
│ - Parse HTML/text to extract data   │
│ - Deduplicate jobs by content hash  │
│ - Sanitize company names            │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│ Stage 3: Resume Matching            │
│ - Load user resume embeddings       │
│ - Calculate semantic similarity     │
│ - Filter jobs by match threshold    │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│ Stage 4: Ranking                    │
│ - Score jobs by multiple factors:   │
│   * Match score (85%)               │
│   * Recency/freshness (7.5%)        │
│   * Source quality (7.5%)           │
└─────────────────┬───────────────────┘
                  ↓
┌─────────────────────────────────────┐
│ Stage 5: Notification               │
│ - Send top matches to user email    │
│ - Include match score explanation   │
└─────────────────┬───────────────────┘
                  ↓
[Pipeline Completed - Results in Dashboard]
```

### Multi-Agent System (LangGraph)

Each stage is powered by specialized AI agents:

```
JobDiscoveryGraph
├── scrape_node → Load job pages using BrowserManager
├── parse_node → Extract job information using LLM
└── dedup_node → Deduplicate and clean data

ResumeMatchingGraph
├── embed_node → Generate resume embeddings
├── search_node → Vector search in Qdrant
└── filter_node → Apply relevance thresholds

RankingGraph
├── score_node → Calculate composite scores
├── prioritize_node → Rank by relevance
└── prepare_node → Format for notification

MessagingGraph
├── draft_node → Generate email content
└── send_node → Send via SMTP

NotificationGraph
├── prepare_node → Prepare notification payload
└── notify_node → Send user notification
```

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 16, TypeScript, Tailwind CSS, NextAuth.js | Web UI, Authentication |
| **Backend** | FastAPI, Pydantic, SQLAlchemy | REST API, Data validation, ORM |
| **Database** | PostgreSQL, Alembic | User data, job results, configuration |
| **Vector DB** | Qdrant | Semantic search, embeddings storage |
| **Task Queue** | Celery, Redis | Background job processing |
| **Scheduling** | APScheduler | Recurring pipeline execution |
| **AI/Agents** | LangGraph, LLM (Claude) | Multi-step pipeline orchestration |
| **Browser** | Playwright | Web scraping with JavaScript support |
| **Auth** | NextAuth.js, JWT | User authentication and session management |
| **Embeddings** | FastEmbed | Local embedding generation |

## 📁 Directory Structure

```
agentic_job_finder/
│
├── agents/                      # Multi-agent pipelines (LangGraph)
│   ├── job_discovery/          # Stage 1: Find and parse jobs
│   │   ├── agent.py           # Agent node implementations
│   │   ├── graph.py           # Pipeline orchestration
│   │   └── state.py           # State management
│   ├── resume_matching/        # Stage 2: Match resumes to jobs
│   ├── ranking/                # Stage 3: Rank matched jobs
│   ├── messaging/              # Stage 4: Generate outreach messages
│   └── notification/           # Stage 5: Notify users
│
├── api/                         # FastAPI Backend
│   ├── main.py                # Application entry point
│   ├── deps.py                # Dependency injection
│   ├── auth/                  # Authentication routes & logic
│   ├── jobs/                  # Job management API
│   ├── users/                 # User management API
│   ├── scrapers/              # Scraper control API
│   └── __pycache__/           # (Ignored in .gitignore)
│
├── db/                         # Database layer
│   ├── base.py               # SQLAlchemy base, session factory
│   ├── models.py             # ORM models (User, Job, Pipeline, etc.)
│   └── migrations/           # Alembic database migrations
│       └── versions/         # Migration files (0001_, 0002_, etc.)
│
├── workers/                    # Background job processing
│   ├── worker.py             # Celery app configuration
│   ├── tasks.py              # Background tasks (pipeline execution)
│   └── utils.py              # Helper utilities
│
├── scrapers/                   # Web scraping modules
│   ├── page_loader.py        # Load job pages (Playwright)
│   ├── generic_scraper.py    # Generic scraper for URLs
│   ├── listing_scraper.py    # Job listing page scraper
│   └── reddit_scraper.py     # Reddit job posts scraper
│
├── extractors/                 # Data extraction & processing
│   ├── job_parser.py         # Parse job postings
│   ├── deduplicator.py       # Remove duplicate jobs
│   ├── company_sanitizer.py  # Clean company names
│   └── seen_jobs.py          # Track processed jobs
│
├── resume/                     # Resume processing
│   ├── pdf_parser.py         # Extract text from PDFs
│   └── pipeline.py           # Resume processing pipeline
│
├── core/                       # Core utilities
│   ├── embeddings.py         # Embedding generation & storage
│   └── qdrant_mcp.py         # Qdrant vector database integration
│
├── models/                     # Configuration models
│   ├── config.py             # Pipeline configuration classes
│   ├── jobs.py               # Job data models
│   └── resume.py             # Resume data models
│
├── tools/                      # Development tools
│   └── browser/              # Browser automation utilities
│       ├── browser_manager.py # Manage browser sessions
│       ├── extract_links.py  # Extract URLs from pages
│       └── extract_text.py   # Extract text from pages
│
├── scheduler/                  # Task scheduling
│   └── scheduler.py          # APScheduler setup & job management
│
├── scripts/                    # Utility scripts
│   ├── start_backend.py      # Start FastAPI server
│   ├── auth_helper.py        # Auto-detect browser auth
│   ├── db_cleanup.py         # Database cleanup utilities
│   ├── preflight.py          # Pre-run checks
│   └── system_reset.py       # Full system reset
│
├── frontend/                   # Next.js Frontend
│   ├── src/
│   │   ├── app/              # Next.js pages (App Router)
│   │   │   ├── dashboard/    # Main dashboard
│   │   │   ├── auth/login/   # Login page
│   │   │   ├── layout.tsx    # Global layout
│   │   │   └── page.tsx      # Home page
│   │   ├── components/       # React components
│   │   │   ├── PipelineHistory.tsx  # Pipeline status & history
│   │   │   └── Providers.tsx        # Auth providers
│   │   ├── lib/              # Utilities
│   │   │   ├── api.ts        # API client functions
│   │   │   └── auth.ts       # NextAuth configuration
│   │   └── types/            # TypeScript types
│   ├── public/               # Static assets
│   ├── package.json          # Dependencies
│   ├── tsconfig.json         # TypeScript config
│   └── next.config.ts        # Next.js config
│
├── data/                       # Runtime data
│   ├── resumes/              # User uploaded resumes
│   └── auth_*.log            # Authentication logs
│
├── local_tests/               # Local development tests
│   ├── test_full_pipeline.py
│   ├── test_job_discovery_agent.py
│   ├── test_matching_pipeline.py
│   └── verify_multi_resume.py
│
├── Configuration Files
│   ├── .env                  # Environment variables (NOT in git)
│   ├── .env.example          # Environment template
│   ├── .gitignore            # Git ignore rules
│   ├── .python-version       # Python version (3.12)
│   ├── requirements.txt      # Python dependencies
│   ├── docker-compose.yml    # Docker services
│   ├── alembic.ini          # Database migration config
│   └── run_migration.py      # Run database migrations
│
└── Test & Monitoring Scripts
    ├── test_scheduler_reschedule.py  # Test scheduler rescheduling
    ├── clear_qdrant.py              # Clear vector database
    └── setup_login.py               # Setup user credentials
```

## 🔧 Setup Instructions

### Prerequisites

- **Python** 3.12+
- **Node.js** 18+ (for frontend)
- **Docker** (for PostgreSQL, Redis, Qdrant)
- **PostgreSQL** 14+ (or use Docker)
- **Redis** (for Celery task queue)
- **Qdrant** (for vector embeddings)

### 1. Clone & Environment Setup

```bash
# Clone repository
git clone <your-repo-url>
cd agentic_job_finder

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Copy environment template
cp .env.example .env
# Edit .env with your configuration:
# - DATABASE_URL: PostgreSQL connection
# - REDIS_URL: Redis connection
# - QDRANT_URL: Qdrant connection
# - OPENAI_API_KEY or ANTHROPIC_API_KEY: LLM API keys
```

### 2. Start Docker Services

```bash
# Start PostgreSQL, Redis, Qdrant in Docker
docker-compose up -d

# Verify services
docker-compose ps
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

```bash
# Run migrations
python run_migration.py           # Core tables
python run_migration_resumes.py   # Resume table
```

### 5. Frontend Setup

```bash
cd frontend
npm install
npm run build  # Build for production
```

## 🚀 Running the Application

### Development Mode

**Terminal 1: Backend**
```bash
python scripts/start_backend.py
# FastAPI runs on http://localhost:8000
# API docs: http://localhost:8000/docs
```

**Terminal 2: Celery Worker**
```bash
celery -A workers.worker.celery_app worker -l info --concurrency=1
```

**Terminal 3: Frontend**
```bash
cd frontend
npm run dev
# Next.js runs on http://localhost:3000
```

**Terminal 4 (Optional): Scheduler/Background Tasks**
```bash
# The scheduler starts with the backend, but you can monitor it separately
```

### Production Deployment

```bash
# Backend
gunicorn -k uvicorn.workers.UvicornWorker api.main:app

# Frontend
cd frontend
npm run build
npm start
```

## 📚 API Documentation

### Quick API Reference

```bash
# Authentication
POST   /auth/login              # Login with credentials
POST   /auth/logout             # Logout
GET    /auth/me                 # Get current user

# Jobs
GET    /jobs                    # List matched jobs
GET    /jobs/runs               # List pipeline runs
GET    /jobs/runs/{run_id}      # Get run details
POST   /jobs/trigger            # Trigger pipeline
DELETE /jobs/runs/{run_id}      # Cancel pipeline run

# Users
GET    /users/me                # Get user profile
PUT    /users/me                # Update preferences
POST   /users/resumes           # Upload resume
GET    /users/resumes           # List resumes

# Scrapers
POST   /scrapers/authenticate   # Authenticate browser session
GET    /scrapers/authenticate/status  # Check auth status
```

See http://localhost:8000/docs for interactive Swagger docs.

## 💾 Database Schema

### Core Tables

#### **users**
Main user accounts table with authentication credentials.
```sql
id                SERIAL PRIMARY KEY
email             VARCHAR UNIQUE, NOT NULL
hashed_password   VARCHAR NOT NULL
is_active         BOOLEAN DEFAULT true
created_at        TIMESTAMP DEFAULT now()
```

#### **user_settings**
User preferences and configuration (per-user settings).
```sql
id                     SERIAL PRIMARY KEY
user_id               VARCHAR UNIQUE FK(users.id)
interval_hours        INTEGER DEFAULT 3        # Scheduling interval
search_queries        JSON DEFAULT []          # Job search keywords
location              VARCHAR DEFAULT "India"  # Job location filter
job_experience        VARCHAR DEFAULT "0"      # Experience level
resume_summary        TEXT NULLABLE            # User's resume summary
notification_email    VARCHAR NULLABLE         # Email for notifications
browser_session       JSON NULLABLE            # Saved browser auth session
updated_at           TIMESTAMP DEFAULT now()
```

#### **links**
Saved job search URLs for automated scraping
```sql
id        SERIAL PRIMARY KEY
user_id   VARCHAR FK(users.id) NOT NULL
url       TEXT NOT NULL
platform  VARCHAR DEFAULT "generic"  # linkedin, wellfound, reddit, generic
is_active BOOLEAN DEFAULT true
created_at TIMESTAMP DEFAULT now()
```

#### **user_resumes**
User-uploaded PDF resumes for job matching
```sql
id            SERIAL PRIMARY KEY
user_id       VARCHAR FK(users.id) NOT NULL
file_name     VARCHAR NOT NULL              # Original filename
file_path     VARCHAR NOT NULL              # Storage path
file_size     INTEGER DEFAULT 0             # Size in bytes
is_active     BOOLEAN DEFAULT true
created_at    TIMESTAMP DEFAULT now()
```

#### **pipeline_runs**
Individual pipeline execution records with scheduling info
```sql
id              SERIAL PRIMARY KEY
user_id         VARCHAR FK(users.id) NOT NULL
celery_task_id  VARCHAR NULLABLE            # Background task ID
triggered_by    VARCHAR;                    # "scheduler" | "manual"
status          VARCHAR DEFAULT "pending"   # pending|running|done|failed|cancelled
execution_count INTEGER DEFAULT 1           # Tracks rescheduled executions
jobs_found      INTEGER DEFAULT 0
jobs_matched    INTEGER DEFAULT 0
jobs_ranked     INTEGER DEFAULT 0
error_message   TEXT NULLABLE
started_at      TIMESTAMP DEFAULT now()
completed_at    TIMESTAMP NULLABLE

# Scheduling fields (PER-PIPELINE)
is_scheduled    BOOLEAN DEFAULT false        # Whether to reschedule
interval_hours  INTEGER DEFAULT 3           # Interval for next execution
```

#### **job_results**
Discovered and ranked jobs from pipeline runs
```sql
id             SERIAL PRIMARY KEY
run_id         VARCHAR FK(pipeline_runs.id) NOT NULL
user_id        VARCHAR FK(users.id) NOT NULL
job_title      VARCHAR NOT NULL
company_name   VARCHAR NOT NULL
job_url        VARCHAR
job_description TEXT
requirements   TEXT
salary_range   VARCHAR NULLABLE
location       VARCHAR NULLABLE
job_source     VARCHAR;                     # Platform: linkedin, wellfound, reddit, etc
match_score    FLOAT DEFAULT 0.0            # Resume match score (0-1)
recency_score  FLOAT DEFAULT 0.0            # Job freshness score (0-1)
source_quality_score FLOAT DEFAULT 0.0      # Platform reliability (0-1)
recruiter_type VARCHAR;                     # "direct" | "recruiter"
final_score    FLOAT DEFAULT 0.0            # Composite score
rank           INTEGER DEFAULT 0            # Ranking position (0 = top)
created_at     TIMESTAMP DEFAULT now()
```

### Table Relationships

```
users (1) ──────────────── (Many) user_settings
          ──────────────── (Many) links
          ──────────────── (Many) user_resumes
          ──────────────── (Many) pipeline_runs
                              ↓
                         (Many) job_results
```

## ⚙️ Configuration Classes

### ScraperConfig
Controls web scraping behavior:
```python
batch_size: int = 5                    # URLs to scrape in parallel
timeout_seconds: int = 30              # Page load timeout
headless: bool = true                  # Run browser headless
disable_images: bool = true            # Disable image loading for speed
block_resources: list = ["stylesheet", "font", "media"]
retry_failed_urls: bool = true
```

### QdrantConfig
Vector database configuration:
```python
url: str  # "http://localhost:6333"
api_key: str | None = None
collection_name: str = "resume_chunks"
embedding_model: str = "BAAI/bge-small-en-v1.5"
batch_size: int = 32
similarity_threshold: float = 0.6
```

### ResumeMatchingConfig
Job-to-resume matching parameters:
```python
chunk_size: int = 512                  # Resume text chunk size
overlap: int = 50                      # Chunk overlap
embedding_batch_size: int = 32
similarity_threshold: float = 0.6      # Minimum match score
reranking_threshold: float = 0.5       # Secondary ranking threshold
```

### RankingConfig
Job ranking algorithm parameters:
```python
match_weight: float = 0.80             # Resume match importance
recency_weight: float = 0.10           # Job freshness importance
source_quality_weight: float = 0.075   # Platform reliability
recruiter_weight: float = 0.025        # Direct vs recruiter
```

### EmailConfig
Email notifications configuration:
```python
smtp_host: str  # SMTP server (e.g., smtp.gmail.com, smtp.office365.com)
smtp_port: int = 587
sender_email: str  # Sender email address
sender_password: str  # SMTP password or app-specific password
use_tls: bool = true
include_unsubscribe: bool = true
```

## 🧪 Testing

### Unit Tests

```bash
# Test scheduler rescheduling (30-second intervals)
python test_scheduler_reschedule.py

# Run local development tests
cd local_tests
python test_full_pipeline.py
python test_matching_pipeline.py
```

### Manual Testing

1. **Start application** (all 3-4 terminals)
2. **Login** at http://localhost:3000
3. **Upload resume** in Settings
4. **Save job search URLs** (LinkedIn, Wellfound, etc.)
5. **Trigger pipeline** and watch dashboard
6. **Monitor logs** in each terminal

## 🔐 Authentication

The app uses **NextAuth.js** with:

- **Credentials provider** (email/password)
- **JWT tokens** for API authentication
- **Session management** via database

Browser sessions are stored separately for authenticated scraping.

## 🤖 How It Works

### Single Pipeline Execution

1. **User triggers pipeline** via Dashboard
2. **Backend creates PipelineRun** with status="pending"
3. **Celery worker picks up task**
4. **Job Discovery Agent** scrapes job listings
5. **Resume Matching Agent** finds relevant jobs
6. **Ranking Agent** scores all matches
7. **Messaging Agent** drafts outreach if needed
8. **Notification Agent** sends results to user
9. **Status updates** in dashboard in real-time

### Scheduled Execution

1. **User enables scheduler** with interval (e.g., every 4 hours)
2. **APScheduler** registers recurring job
3. **Every 4 hours**, pipeline automatically triggers
4. **Execution count** increments
5. **Results accumulate** in dashboard

## 🐛 Debugging

### Check Logs

```bash
# Backend logs (in start_backend.py terminal)
# Look for [pipeline], [agent], [scheduler] prefixes

# Celery worker logs
# Look for task IDs and completion status

# Frontend logs (browser console)
# Check for API errors or state issues
```

### Common Issues

| Issue | Solution |
|-------|----------|
| Database connection error | Check `DATABASE_URL` in `.env` and ensure PostgreSQL is running |
| Qdrant connection error | Verify `QDRANT_URL` and check `/health` endpoint |
| Jobs not appearing | Check browser session auth; navigate to /scrapers/authenticate |
| Pipeline stuck | Check Celery worker is running; verify task wasn't killed |
| Resume upload fails | Ensure `/data/resumes/` directory exists and is writable |

## 📝 Environment Variables

Copy `.env.example` to `.env` and configure the following variables:

### **Database & Cache**
```env
# PostgreSQL Database
DATABASE_URL=postgresql+asyncpg://<user>:<password>@db:5432/job_agent
DB_PASSWORD=your_secure_password
DB_NAME=job_agent

# Redis Cache & Message Broker
REDIS_URL=redis://redis:6379/0
```

### **Email Configuration (SMTP)**
```env
# SMTP Server Configuration
# Supports Gmail, Outlook, custom SMTP servers, etc.
EMAIL_SMTP_HOST=smtp.gmail.com              # Your SMTP server
EMAIL_SMTP_PORT=587                         # Usually 587 (TLS) or 465 (SSL)
EMAIL_SENDER=your-email@gmail.com           # Sender email address
EMAIL_PASSWORD=your_app_password             # SMTP password or app-specific password
```

**Example Configurations:**

*Gmail (requires App Password):*
```env
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your_16_digit_app_password
```

*Outlook/Office 365:*
```env
EMAIL_SMTP_HOST=smtp.office365.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=your-email@outlook.com
EMAIL_PASSWORD=your_outlook_password
```

*Custom SMTP Server:*
```env
EMAIL_SMTP_HOST=mail.yourdomain.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=noreply@yourdomain.com
EMAIL_PASSWORD=your_smtp_password
```

### **Vector Database (Qdrant)**
```env
# Qdrant Cloud or Local
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=your_qdrant_api_key          # Optional, for cloud instances
```

### **LLM & Embeddings**
```env
# Mistral AI (for embeddings and LLM)
MISTRAL_API_KEY=your_mistral_api_key_here

# LangChain Tracing (optional, for debugging)
LANGCHAIN_API_KEY=your_langchain_api_key_here
LANGCHAIN_PROJECT=agentic-job-finder
```

### **Authentication & Security**
```env
# JWT Token Signing
JWT_SECRET_KEY=your_jwt_secret_key_here     # Use a strong random string

# NextAuth Configuration
AUTH_SECRET=your_nextauth_secret_here       # Use a strong random string
AUTH_TRUST_HOST=true
NEXTAUTH_URL=http://localhost:3000

# Google OAuth (for frontend authentication)
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

### **Frontend API Integration**
```env
# Backend API URL (public, visible to client)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### **Application Settings**
```env
# Development vs Production
DEVELOPMENT_MODE=true     # Set to false for production
```

### **Complete Setup Checklist**

- [ ] Copy `.env.example` to `.env`
- [ ] Set `DATABASE_URL` with your PostgreSQL credentials
- [ ] Set `DB_PASSWORD` to a strong password
- [ ] Configure SMTP settings: `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SENDER`, `EMAIL_PASSWORD`
- [ ] Set `MISTRAL_API_KEY` for LLM operations
- [ ] Generate `JWT_SECRET_KEY` and `AUTH_SECRET` (use: `openssl rand -hex 32`)
- [ ] Configure Google OAuth IDs if using frontend auth
- [ ] Test database: `python scripts/preflight.py`

## � Pipeline Execution & Scheduling

### Pipeline Status Lifecycle

Each pipeline run progresses through distinct states:

| Status | Description | Display | Behavior |
|--------|-------------|---------|----------|
| **pending** | Pipeline created and queued to run | 🔵 Queued | Waiting for worker to pick it up |
| **running** | Pipeline is currently executing | 🔵 Running | Job discovery & matching in progress; shows live progress |
| **done** | Pipeline successfully completed | ✅ Completed | Results available in dashboard; if scheduled, waits for next interval |
| **failed** | Pipeline encountered an error | ❌ Failed | Check error message; no reschedule occurs |
| **cancelled** | Pipeline was manually stopped by user | ⏹️ Cancelled | User clicked cancel button; terminal state |

### Scheduled Pipeline Behavior

When a pipeline is triggered with **Auto-Scheduling enabled**:

1. **First Run**: Status progresses `pending → running → done`
2. **Waiting Period**: Stays in `done` state while scheduler waits for interval to elapse
3. **Next Execution**: Automatically resets to `pending` when interval passes
4. **Reuse**: Same pipeline ID is reused (execution_count increments)
5. **Display**: Shows as "Pipeline [ID] - Execution #1", then "#2", etc.

**Example Timeline** (3-hour interval):
```
14:00 - Execution #1: pending → running → done (discovers 10 jobs)
14:01-16:59 - Waiting for interval...
17:00 - Execution #2: pending → running → done (discovers 8 new jobs)
17:01-19:59 - Waiting for interval...
20:00 - Execution #3: pending → running... (currently executing)
```

### Non-Scheduled Pipeline Behavior

When triggered with Auto-Scheduling **disabled**:
- Follows: `pending → running → done` (terminal state)
- Pipeline completes and appears in history
- No automatic rescheduling occurs
- User can manually trigger again if needed
## 🤖 Multi-Agent System Details

### Agent Architecture (LangGraph)

The system uses **LangGraph** to coordinate five specialized agents:

#### **1. Job Discovery Agent** (`agents/job_discovery/`)
Discovers and parses job listings from multiple sources.

**Nodes:**
- `scrape_node`: Uses Playwright to load job pages with authentication
- `parse_node`: Extracts structured job data using LLM
- `dedup_node`: Removes duplicate jobs using content hashing

**Outputs:**
- List of discovered jobs with metadata
- Count tracked in `pipeline_runs.jobs_found`

**Example Flow:**
```
User URLs → Load with Browser → Extract Links → Parse HTML → Dedup → Job List
```

#### **2. Resume Matching Agent** (`agents/resume_matching/`)
Matches user resumes against discovered jobs using semantic similarity.

**Nodes:**
- `chunk_filter_node`: Filters jobs by basic text matching
- `embed_node`: Generates embeddings for jobs and resume chunks
- `search_node`: Vector search using Qdrant (cosine similarity)
- `rerank_node`: Applies secondary ranking thresholds

**Outputs:**
- Jobs that exceed matching threshold (default: 0.6)
- Match scores for each job
- Count tracked in `pipeline_runs.jobs_matched`

**Embedding Details:**
- Model: `BAAI/bge-small-en-v1.5` (384-dim vectors)
- Chunking: 512-char chunks with 50-char overlap
- Distance: Cosine similarity (normalized to 0-1)

#### **3. Ranking Agent** (`agents/ranking/`)
Scores and prioritizes matched jobs by relevance.

**Scoring Formula:**
```
final_score = (
    match_score * 0.80 +           # 80% - Resume match relevance
    recency_score * 0.10 +          # 10% - Job freshness (last 7 days)
    source_quality * 0.075 +        # 7.5% - Platform reliability (LinkedIn > Wellfound)
    recruiter_weight * 0.025        # 2.5% - Direct (1.0) vs Recruiter (0.5) posting
)
```

**Outputs:**
- Ranked job list (highest score first)
- All component scores for transparency
- Count tracked in `pipeline_runs.jobs_ranked`

#### **4. Messaging Agent** (`agents/messaging/`)
Generates AI-powered outreach messages (optional feature).

**Capabilities:**
- Personalized cover letter generation
- Skill highlighting based on job requirements
- Tone and style customization

**Outputs:**
- Outreach template with placeholders
- Ready for user review and sending

#### **5. Notification Agent** (`agents/notification/`)
Formats and sends results to users via email.

**Templates:**
- HTML email digest with rankings
- Match score explanations
- Direct links to job postings
- Unsubscribe option

**Configuration:**
- Uses SMTP for reliable delivery
- Scheduled batch sending (configurable)
- Reply-to setup for engagement tracking

### Agent State Management

Each agent uses **TypedDict** for state management:

```python
class AgentState(TypedDict):
    user_id: str                    # User identifier
    urls: list[str]                 # Job URLs to process
    jobs: list[Job]                 # Discovered jobs
    matched_jobs: list[Job]         # Resume-matched jobs
    ranked_jobs: list[Job]          # Final ranked results
    run_id: str                      # Pipeline run ID
    error: str | None               # Error message if failed
```

