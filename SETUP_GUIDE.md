# Platform-Independent Setup Guide

**Supported**: Linux, macOS, Windows (Git Bash/WSL/PowerShell), BSD

---

## 🚀 Quick Start

### Linux / macOS / BSD
```bash
bash setup.sh
```

### Windows - Git Bash (Recommended)
1. Install [Git for Windows](https://git-scm.com/download/win)
2. Open Git Bash
3. `bash setup.sh`

### Windows - WSL
```bash
wsl --install  # Then restart and run: bash setup.sh
```

### Windows - PowerShell
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup.ps1
```

### Windows - Command Prompt
```cmd
setup.bat
```

---

## 📋 Setup Scripts

| Script | Platform | Requirements |
|--------|----------|--------------|
| `setup.sh` | Linux, macOS, WSL, Git Bash | bash, python3, pip |
| `setup.bat` | Windows cmd | Git Bash or fallback instructions |
| `setup.ps1` | PowerShell 7+ | PowerShell (no bash needed) |

**What they do:**
- Create and activate Python virtual environment
- Install dependencies from `requirements.txt`
- Setup Playwright (web scraping)
- Create required directories
- Initialize frontend dependencies

---

## 🔧 Manual Setup (If Scripts Fail)

### Linux/macOS/WSL
```bash
git clone <repo-url> && cd agentic_job_finder
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
mkdir -p data/resumes
cd frontend && npm install && cd ..
docker-compose up -d
```

### Windows (cmd.exe)
```cmd
git clone <repo-url> && cd agentic_job_finder
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
playwright install chromium
mkdir data\resumes
cd frontend && npm install && cd ..
docker-compose up -d
```

---

## ❓ Troubleshooting

| Issue | Solution |
|-------|----------|
| bash not found on Windows | Install [Git for Windows](https://git-scm.com/download/win) or use WSL |
| Permission denied on macOS | `chmod +x setup.sh setup.bat setup.ps1` |
| PowerShell execution error | Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| Virtual env not activating | Verify `.venv/bin/activate` exists; recreate: `rm -rf .venv && python3 -m venv .venv` |
| Docker not found | Install [Docker Desktop](https://www.docker.com/products/docker-desktop) |
| Playwright issues | `playwright install chromium` |

---

## ✅ After Setup

Verify installation:
```bash
docker-compose ps              # Check all services running
source .venv/bin/activate      # Activate Python env
python -c "import fastapi"     # Verify dependencies
```

Then follow [README.md](README.md) to run the application.

