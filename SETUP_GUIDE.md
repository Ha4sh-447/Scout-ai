# Setup Guide — Agentic Job Finder

**Supported**: Linux, macOS, Windows (any terminal with Python 3.9+)

---

## 🚀 Quick Start

```bash
git clone https://github.com/Ha4sh-447/Scout-ai.git
cd Scout-ai
python setup.py        # python3 on Linux/macOS if needed
```

The script walks you through every step in a **polished, interactive CLI** — no bash or PowerShell knowledge required.

---

## 🔎 Check Prerequisites Only

```bash
python setup.py --check-only
```

Prints a dependency table (Python, pip, Docker, Node/npm, Git) and exits — nothing is installed.

---

## 📋 What `setup.py` Does

| Step | Action |
|------|--------|
| 1 | Check prerequisites (Python, pip, Docker, Node/npm, git) |
| 2 | Create `.env` from `.env.example` if missing |
| 3 | Create Python virtual environment (`.venv`) |
| 4 | Install Python dependencies from `requirements.txt` |
| 5 | Install Playwright Chromium browser *(optional — asked)* |
| 6 | Create `data/resumes/` directory |
| 7 | Install frontend npm dependencies *(optional — asked)* |
| 8 | Start Docker services (`docker compose up -d`) *(optional — asked)* |
| 9 | Run Alembic database migrations *(optional — asked)* |
| 10 | Run preflight checks (`scripts/preflight.py`) |

---

## 🔧 Manual Setup (If Script Fails)

```bash
# 1. Clone and enter the project
git clone https://github.com/Ha4sh-447/Scout-ai.git && cd Scout-ai

# 2. Copy environment file and fill in your keys
cp .env.example .env

# 3. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 5. Create data directories
mkdir -p data/resumes

# 6. Install frontend dependencies
cd frontend && npm install && cd ..

# 7. Start Docker services
docker compose up -d

# 8. Run migrations
cd db/migrations && alembic upgrade head && cd ../..

# 9. Run preflight checks
python scripts/preflight.py
```

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| `python: command not found` | Use `python3` on Linux/macOS, or install Python from [python.org](https://www.python.org/downloads/) |
| Permission denied (macOS/Linux) | `chmod +x setup.py` |
| Docker not found | Install [Docker Desktop](https://www.docker.com/products/docker-desktop) |
| Playwright issues | Run: `playwright install chromium` inside the venv |
| venv not activating | Recreate: `rm -rf .venv && python3 -m venv .venv` |
| Migrations fail | Ensure Docker services are up: `docker compose ps` |

---

## ✅ After Setup

```bash
docker compose ps                        # All services should be "running"
source .venv/bin/activate                # Activate venv (Linux/macOS)
python -c "import fastapi; print('OK')" # Verify dependencies
```

Then follow [README.md](README.md) to run the application.
