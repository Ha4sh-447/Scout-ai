# 🤖 Agentic Job Finder

An intelligent job discovery platform powered by AI agents that finds, matches, ranks, and helps you reach out to relevant job opportunities personalized to your profile.

**Status**: ✅ Production Ready | **Tech Stack**: Python, FastAPI, LangChain, PostgreSQL, Redis, Qdrant, React/Next.js

---

## 🎯 What It Does

1. **Discovers** jobs from LinkedIn, Indeed, Reddit, and custom URLs
2. **Matches** jobs to your resume using semantic search (vector DB)
3. **Ranks** jobs by relevance, recency, and source quality
4. **Generates** personalized outreach messages (email & LinkedIn)
5. **Notifies** you via email with job digest
6. **Schedules** recurring pipeline runs

---

## 📋 System Requirements

### Minimum Requirements
- **OS**: Linux, macOS, Windows (WSL2/Git Bash), or BSD
- **Python**: 3.9+
- **Docker**: Latest version with Docker Compose
- **Memory**: 4GB RAM minimum (8GB recommended)
- **Disk**: 5GB for Docker images and database

### Required Accounts
- **Google Account** (for Gmail SMTP email sending) ✅ **Required**
- **LinkedIn Account** (for job scraping and personalization) ✅ **Required**  
- **Mistral AI Account** (for embeddings API) ✅ **Required**
- **LangChain Account** (optional, for tracing & debugging) ⚠️ **Optional**
- **Google OAuth** (optional, for OAuth authentication) ⚠️ **Optional**

---

## ⚡ Quick Start (5 Minutes)

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/agentic_job_finder.git
cd agentic_job_finder
```

### 2. Setup Environment Variables
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials (see Configuration section below)
nano .env  # or use your preferred editor
```

### 3. Start Docker Services
```bash
# Start PostgreSQL, Redis, Qdrant, and other services
docker-compose up -d

# Verify services are running
docker-compose ps
```

### 4. Configure & Run
```bash
# Activate Python environment
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate     # On Windows

# Run full setup (installs dependencies, initializes DB)
bash setup.sh              # On Linux/macOS/WSL
# or
setup.bat                  # On Windows Command Prompt
# or
.\setup.ps1               # On Windows PowerShell

# Authenticate with LinkedIn (see section below)
python scripts/auth_helper.py --user-id YOUR_USER_ID --platforms linkedin

# Start the API server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001

# In another terminal, start Celery worker
celery -A workers.worker worker --loglevel=info

# In another terminal, start the frontend
cd frontend && npm run dev
```

---

## 🔧 Complete Setup Instructions

### Step 1: Prerequisites Installation

#### On Linux/macOS
```bash
# Install Homebrew (macOS only)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required tools
brew install python docker docker-compose git

# Or using apt (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3 python3-pip docker docker-compose git
```

#### On Windows
1. **Download Git**: https://git-scm.com/download/win
2. **Download Docker Desktop**: https://www.docker.com/products/docker-desktop
3. **Download Python**: https://www.python.org/downloads/
4. Add them to PATH and restart terminal

### Step 2: Clone & Navigate
```bash
git clone https://github.com/yourusername/agentic_job_finder.git
cd agentic_job_finder
```

### Step 3: Create Python Virtual Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate          # Linux/macOS/WSL
# or
.venv\Scripts\activate             # Windows
```

### Step 4: Configure Environment Variables

#### 4.1 Copy Example File
```bash
cp .env.example .env
```

#### 4.2 Edit `.env` with Required Credentials

**API Keys** (Get from their services):
```bash
LANGCHAIN_API_KEY=<your-langchain-key>
MISTRAL_API_KEY=<your-mistral-api-key>
JWT_SECRET_KEY=<random-secret-key>
```

**Database** (Pre-configured - generally don't change):
```bash
DATABASE_URL=postgresql+asyncpg://<user>:<db_password>@db:5432/<db_name>
DB_USER=<user>
DB_PASSWORD=<db_password>
DB_NAME=<db_name>

```

**Email Configuration (Gmail)**:
```bash
EMAIL_SENDER=your-email@gmail.com
EMAIL_SMTP_HOST=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_PASSWORD=your-16-digit-app-password
```

**How to get Gmail App Password:**
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Enable 2-Factor Authentication first if not already enabled
3. Select **Mail** and **Other (custom name)** → type `Job Finder`
4. Copy the 16-digit password and add to `.env` as `EMAIL_PASSWORD`

**Redis & Qdrant** (Default - keep as is for Docker):
```bash
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
```

### Step 5: Start Docker Services
```bash
# Start all services (PostgreSQL, Redis, Qdrant)
docker-compose up -d

# Verify all services are healthy
docker-compose ps

# Expected output:
# NAME              STATUS          PORTS
# job_finder_db     Up 2 minutes     5432/tcp
# job_finder_redis  Up 2 minutes     6379/tcp
# job_finder_qdrant Up 2 minutes     6333/tcp
```

### Step 6: Initialize Database & Install Dependencies
```bash
# Run the setup script (this will):
# - Install Python dependencies
# - Initialize the database
# - Create necessary tables
bash setup.sh              # Linux/macOS/WSL
# or
setup.bat                  # Windows (cmd)
# or
.\setup.ps1               # Windows (PowerShell)
```

**What setup.sh does:**
```bash
# 1. Activates Python virtual environment
source .venv/bin/activate

# 2. Installs Python dependencies from requirements.txt
pip install -r requirements.txt

# 3. Installs Playwright browsers (for web scraping)
playwright install chromium

# 4. Creates data directories
mkdir -p data/resumes

# 5. Runs database migrations
cd db/migrations && alembic upgrade head

echo "✅ Setup complete!"
```

---

## 🔐 LinkedIn Authentication (Important!)

This is **critical** for personalized job scraping with your LinkedIn profile.

### How It Works
The `auth_helper.py` script opens your browser, lets you log into LinkedIn, and saves your authenticated session so the bot can scrape jobs personalized to your profile.

### How to Run

#### Get Your User ID

You **must** have a user account first. Here are 4 ways to get your user ID:

**Option 1: Via Frontend (Easiest)**
```bash
# In one terminal, start the API:
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001

# In another terminal, start the frontend:
cd frontend && npm run dev

# Then:
# 1. Visit http://localhost:3000
# 2. Click "Sign Up" and create an account
# 3. After signup, you'll see your User ID on the welcome screen
# 4. Copy the ID (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
```

**Option 2: Via Database**
```bash
# Query PostgreSQL directly:
psql -U <user> -d <db_name> -h localhost -c \
  "SELECT id, email, created_at FROM users ORDER BY created_at DESC LIMIT 1;"

# Output:
#                  id                  |        email         |      created_at
# 85e28c83-38b2-4d81-be88-b4bfe56d3c6b | your-email@example.com | 2025-03-29 12:00:00

# Copy the id column
```

**Option 3: Via API (After Getting Token)**
```bash
# First, get your authentication token from signup response, then:
curl -X GET http://localhost:8001/users/me \
  -H "Authorization: Bearer YOUR_TOKEN"

# Response will show your user object with "id" field
# Example: "id": "85e28c83-38b2-4d81-be88-b4bfe56d3c6b"
```

**Option 4: Via Docker Logs**
```bash
# Watch API logs during signup:
docker-compose logs -f job_finder_api | grep "user"

# Look for messages like: "New user created: 85e28c83-38b2-4d81-be88-b4bfe56d3c6b"
```

#### Store Your User ID for Easy Access
```bash
# Once you have your User ID, save it as an environment variable:
export USER_ID="85e28c83-38b2-4d81-be88-b4bfe56d3c6b"

# Verify it's set:
echo $USER_ID

# Now use it in commands:
python scripts/auth_helper.py --user-id $USER_ID --platforms linkedin
```

#### Run Authentication Helper
```bash
# Make sure your virtual environment is activated
source .venv/bin/activate

# Run the auth helper
python scripts/auth_helper.py --user-id $USER_ID --platforms linkedin

# Expected output:
# [INFO] Opening browser for LinkedIn authentication...
# [INFO] Waiting for user to log in (30s timeout)...
# [INFO] ✓ Session saved successfully for user 85e28c83-38b2-4d81-be88-b4bfe56d3c6b
```

#### What You Need to Do
1. A browser window opens automatically
2. Log in with your LinkedIn credentials
3. Approve any permission requests
4. **Wait for the script to finish** (don't close the browser)
5. You should see: `✓ Session saved successfully`

### Why This Matters
- ✅ Gets personalized job recommendations based on your profile
- ✅ Scrapes jobs matching your skills and experience
- ✅ Handles LinkedIn's anti-bot protections
- ✅ Your session is encrypted and stored securely in the database

### Troubleshooting Authentication
```bash
# If timeout (browser closes too fast):
# - Run from the project root directory
cd /path/to/agentic_job_finder

# Check the log file:
tail -f data/auth_helper.log

# Re-run authentication:
python scripts/auth_helper.py --user-id YOUR_USER_ID --platforms linkedin --timeout 60
```

---

## 🚀 Running the Application

### Terminal 1: Start Database & Services
```bash
docker-compose up -d
docker-compose logs -f  # Monitor logs (Ctrl+C to exit)
```

### Terminal 2: Start API Server
```bash
source .venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8001

# Expected output:
# Uvicorn running on http://0.0.0.0:8001
# Press CTRL+C to quit
```

### Terminal 3: Start Celery Worker (Job Processing)
```bash
source .venv/bin/activate
celery -A workers.worker worker --loglevel=info

# Expected output:
# celery@hostname ready to accept tasks
```

### Terminal 4: Start Frontend (React/Next.js)
```bash
cd frontend

# First time only: Verify .env is configured correctly
# Check that NEXT_PUBLIC_API_URL=http://localhost:8001 and NEXTAUTH_URL=http://localhost:3000
cat .env | grep -E "NEXT_PUBLIC_API_URL|NEXTAUTH_URL"

# Install dependencies
npm install

# Start development server
npm run dev

# Expected output:
# ▲ Next.js 14.0.0
# - Local: http://localhost:3000
```

**Frontend .env Configuration:**
The frontend comes with a `.env` file pre-configured. If you need to customize it:
```bash
# Edit frontend/.env with your settings
nano frontend/.env

# Key settings:
NEXT_PUBLIC_API_URL=http://localhost:8001  # Match your API server
NEXTAUTH_URL=http://localhost:3000
AUTH_SECRET=<generate-with: openssl rand -base64 32>
NEXTAUTH_URL=http://localhost:3000
```

### Access the Application
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8001/docs (Swagger UI)
- **Health Check**: `curl http://localhost:8001/health`

---

## 📊 Your First Pipeline Run

### Step 1: Create a User Account
```bash
# Via the frontend:
# 1. Visit http://localhost:3000
# 2. Click "Sign Up"
# 3. Create account with email
# 4. Note your User ID from welcome screen
```

### Step 2: Authenticate LinkedIn (if not done)
```bash
python scripts/auth_helper.py --user-id YOUR_USER_ID --platforms linkedin
```

### Step 3: Upload Your Resume
```bash
# Via the frontend:
# 1. Go to Dashboard → "My Resumes"
# 2. Upload your resume (PDF/DOCX)
# 3. Wait for processing (30-60 seconds)
```

### Step 4: Configure Search Settings
```bash
# Via the frontend:
# 1. Go to Dashboard → "Preferences"
# 2. Set:
#    - Search keywords: "Python Developer", "Backend Engineer"
#    - Location: "India"
#    - Experience: "2+ years"
#    - Notification email: your-email@gmail.com
# 3. Click "Save"
```

### Step 5: Add Job Search URLs
```bash
# Via the frontend:
# 1. Go to Dashboard → "Search URLs"
# 2. Add URLs like:
#    - https://www.linkedin.com/jobs/search/?keywords=python%20developer
#    - https://www.indeed.com/jobs?q=backend+engineer
# 3. Click "Save"
```

### Step 6: Trigger Pipeline
```bash
# Via the frontend:
# 1. Go to Dashboard → "Pipeline History"
# 2. Click "Trigger Pipeline" button
# 3. Watch status in real-time

# OR via API:
curl -X POST http://localhost:8001/jobs/trigger \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "queries": ["Python Developer"],
    "location": "India",
    "experience": "2"
  }'
```

### Step 7: Monitor Progress
```bash
# Watch real-time logs:
docker-compose logs -f job_finder_celery

# Common stages:
# Stage 1: Job Discovery (scraping)
# Stage 2: Resume Matching (semantic search)
# Stage 3: Ranking (relevance scoring)
# Stage 4: Messaging (generating outreach)
# Stage 5: Notification (sending email)
```

### Step 8: Check Results
```bash
# Once pipeline completes, you'll see:
# 1. Jobs in Dashboard "Matched Listings" tab
# 2. Email notification (check inbox!)
# 3. Job preview on each card with:
#    - Match score (semantic similarity)
#    - Final rank
#    - Suggested outreach messages
```

---

## 🧠 How It Works

### Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. JOB DISCOVERY                                                │
│    ├─ Scrape LinkedIn job posts (authenticated)                 │
│    ├─ Extract: title, company, location, skills, salary        │
│    └─ Deduplicate within batch                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. RESUME MATCHING (Stage 1: Chunk Filtering)                   │
│    ├─ Generate resume embeddings (Mistral AI)                   │
│    ├─ Create Qdrant vectors (semantic search)                   │
│    ├─ Query job descriptions against resume                     │
│    └─ Filter jobs below match threshold (0.45)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. RESUME MATCHING (Stage 2: Reranking)                          │
│    ├─ Query full resume against top candidates                  │
│    └─ Blend chunk score + full resume score                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. RANKING                                                       │
│    ├─ Weight by: match_score (85%) + recency (7.5%) + source (7.5%)
│    └─ Generate final rank (1-100)                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. MESSAGING                                                     │
│    ├─ Find hiring decision makers (email/LinkedIn URL)          │
│    ├─ Generate personalized outreach message                    │
│    └─ Store drafts (email + LinkedIn)                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. NOTIFICATION                                                  │
│    ├─ Build HTML email digest                                   │
│    ├─ Send via Gmail SMTP                                       │
│    └─ Store delivery status                                     │
└─────────────────────────────────────────────────────────────────┘
```

---

##  Troubleshooting

### "Docker services not starting"
```bash
# Check logs
docker-compose logs

# Restart services
docker-compose down
docker-compose up -d

# Ensure no port conflicts (5432, 6379, 6333)
sudo netstat -tlnp | grep -E ':(5432|6379|6333)'
```

### "LinkedIn authentication timeout"
```bash
# Increase timeout and run from project root
cd /path/to/agentic_job_finder
python scripts/auth_helper.py --user-id YOUR_USER_ID --platforms linkedin --timeout 120
```

### "Email not sending"
```bash
# Check Gmail configuration in .env
 1. Verify app password is correct (no spaces)
 2. Check 2FA is enabled
 3. View logs: docker-compose logs job_finder_api
```

### "Jobs not being matched"
```bash
# Check resume was uploaded and processed
# Check Qdrant connection
curl http://localhost:6333/health

# Check embeddings were created
SELECT COUNT(*) FROM job_results WHERE match_score > 0;

# Check min_match_score threshold (default: 0.45)
# Lower if needed in config.py
```

### "Pipeline stuck or slow"
```bash
# Check Celery worker is running
docker-compose logs job_finder_celery

# Monitor resource usage
docker stats

# If needed, increase worker concurrency
celery -A workers.worker worker --loglevel=info --concurrency=4
```

---

## 📝 Configuration Reference

### Complete Environment Variables (Backend `.env`)

| Variable | Purpose | Example | Required |
|----------|---------|---------|----------|
| **Database** | | | |
| `DATABASE_URL` | PostgreSQL connection (used in docker-compose) | `postgresql+asyncpg://<user>:<user>%40%241711@db:5432/<db_name>` | ✅ |
| `DB_USER` | PostgreSQL username (for docker-compose) | `<user>` | ⚠️ Optional |
| `DB_PASSWORD` | PostgreSQL password (for docker-compose) | `<user>@$1711` | ⚠️ Optional |
| `DB_NAME` | PostgreSQL database name (for docker-compose) | `<db_name>` | ⚠️ Optional |
| **Queue & Cache** | | | |
| `REDIS_URL` | Redis connection for Celery | `redis://redis:6379/0` | ✅ |
| `QDRANT_URL` | Vector database connection | `http://qdrant:6333` | ✅ |
| `QDRANT_API_KEY` | Qdrant API key (optional) | `your_key_here` | ⚠️ Optional |
| **API Keys & Tracing** | | | |
| `MISTRAL_API_KEY` | Mistral embeddings API key | Get from mistral.ai | ✅ |
| `LANGCHAIN_API_KEY` | LangChain tracing API key | Get from langchain.com | ⚠️ Optional |
| `LANGCHAIN_TRACING_V2` | Enable LangChain tracing | `true` or `false` | ⚠️ Optional |
| `LANGCHAIN_PROJECT` | LangChain project name | `agentic-job-finder` | ⚠️ Optional |
| **Authentication** | | | |
| `JWT_SECRET_KEY` | JWT token signing secret | `your-random-secret-here` | ✅ |
| **Email (Gmail)** | | | |
| `EMAIL_SENDER` | Gmail address for sending emails | `your-email@gmail.com` | ✅ |
| `EMAIL_PASSWORD` | Gmail app-specific password (16 digits) | From myaccount.google.com/apppasswords | ✅ |
| `EMAIL_SMTP_HOST` | Gmail SMTP server | `smtp.gmail.com` | ✅ |
| `EMAIL_SMTP_PORT` | Gmail SMTP port (TLS) | `587` | ✅ |
| **Application** | | | |
| `DEVELOPMENT_MODE` | Enable development features | `true` or `false` | ⚠️ Optional |

### Frontend Environment Variables (`.env` in `/frontend`)

| Variable | Purpose | Example | Required |
|----------|---------|---------|----------|
| `NEXT_PUBLIC_API_URL` | Backend API endpoint | `http://localhost:8001` | ✅ |
| `NEXTAUTH_URL` | NextAuth base URL | `http://localhost:3000` | ✅ |
| `AUTH_SECRET` | NextAuth encryption secret | Generate with: `openssl rand -base64 32` | ✅ |
| `AUTH_TRUST_HOST` | Trust auth headers | `true` | ✅ |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | Get from Google Cloud Console | ⚠️ Optional |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | Get from Google Cloud Console | ⚠️ Optional |

### Pipeline Configuration

Edit `models/config.py` to customize:
```python
class ResumeMatchingConfig:
    min_match_score = 0.45      # Minimum semantic similarity
    rerank_top_n = 50           # Top candidates for reranking
    top_k_chunks = 15           # Resume chunks to query
    full_resume_weight = 0.35   # Blend weight for full resume
```

### Scheduler Configuration

The pipeline can run on a recurring schedule. Configure it via API or database:

**Via Database (Direct):**
```sql
-- Set pipeline to run every 3 hours
UPDATE user_settings 
SET interval_hours = 3 
WHERE user_id = 'YOUR_USER_ID';

-- Enable scheduling for all pipeline runs
UPDATE pipeline_runs 
SET is_scheduled = true, interval_hours = 3 
WHERE user_id = 'YOUR_USER_ID' AND is_scheduled = false;
```

**Via Frontend:**
- Go to **Dashboard → Settings → Preferences**
- Set "Pipeline Interval (hours)" to your desired value
- Save settings

**Default Behavior:**
- Interval: 3 hours (configurable per user)
- Runs automatically on app startup (if enabled)
- Gracefully handles missed runs if app was offline

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:8001/docs (when running)
- **Installation Setups**: See [SETUP_GUIDE.md](SETUP_GUIDE.md) for platform-specific instructions

---

## ✨ Key Features Implemented

- ✅ **AI-Powered Job Discovery**: Finds relevant jobs across multiple platforms
- ✅ **Semantic Resume Matching**: LLM-based matching with vector embeddings
- ✅ **Smart Ranking**: Multi-factor relevance scoring
- ✅ **Personalized Outreach**: AI-generated connection messages
- ✅ **Email Notifications**: HTML digest emails with summaries
- ✅ **Scheduled Pipelines**: Recurring job discovery (configurable intervals)
- ✅ **Production Ready**: Docker-based, scalable architecture

---
