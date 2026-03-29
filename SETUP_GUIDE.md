# Platform-Independent Setup Guide

**Status**: ✅ Fully platform-independent
**Supported**: Linux, macOS, Windows (Git Bash/WSL/PowerShell), BSD

---

## 🎯 Choose Your Platform

### 🐧 **Linux / macOS / BSD (Recommended)**

```bash
bash setup.sh
```

**Why this works best:**
- ✅ Full ANSI color support
- ✅ Native bash shell
- ✅ All features available
- ✅ Fastest setup

**Requirements:**
- bash (included by default)
- python3
- pip

---

### 🪟 **Windows with Git Bash**

```bash
bash setup.sh
```

**Setup:**
1. Install [Git for Windows](https://git-scm.com/download/win)
2. Open "Git Bash"
3. Navigate to project: `cd path/to/agentic_job_finder`
4. Run: `bash setup.sh`

**Why Git Bash:**
- ✅ Native bash experience on Windows
- ✅ Full compatibility with setup.sh
- ✅ Same commands as Linux/macOS
- ✅ Most developer-friendly

---

### 🪟 **Windows with WSL (Windows Subsystem for Linux)**

```bash
# In WSL terminal
bash setup.sh
```

**Setup:**
1. Open PowerShell as Administrator
2. Run: `wsl --install`
3. Restart computer
4. Open WSL: search for "Ubuntu" or your distro
5. Clone repo and run: `bash setup.sh`

**Why WSL:**
- ✅ Full Linux environment on Windows
- ✅ Native Docker support (WSL 2)
- ✅ Best performance
- ✅ Professional development setup

---

### 🪟 **Windows Command Prompt (cmd.exe)**

Use the batch file wrapper:

```cmd
setup.bat
```

**What it does:**
- ✅ Detects if bash is installed
- ✅ Routes to Git Bash if available
- ✅ Provides instructions if bash not found
- ✅ Helps Windows users get started

---

### 🪟 **Windows PowerShell 7+**

```powershell
# Allow script execution (one-time)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run setup
.\setup.ps1
```

**Pros:**
- ✅ Native Windows shell
- ✅ Modern feature set
- ✅ Good integration with Windows tools

**Cons:**
- ⚠️ Some features may vary from bash

**Installation:**
- [PowerShell 7+](https://github.com/PowerShell/PowerShell)

---

## 📋 What Each Setup Script Does

### `setup.sh` - Main Script (Bash)

**Platform-independent features:**
- ✅ Detects OS type (Linux/macOS/Windows)
- ✅ Handles both color output and plain text
- ✅ Virtual env activation for both Unix and Windows
- ✅ Conditional permission management
- ✅ Detects Docker vs Docker Compose command
- ✅ Skip chmod on Windows

**Best for:**
- Linux, macOS, WSL, Git Bash
- Power users, developers
- CI/CD environments

---

### `setup.bat` - Windows Batch Wrapper

**What it does:**
1. Checks if bash is available
2. If yes → runs `bash setup.sh`
3. If no → shows installation instructions

**Best for:**
- Windows users new to command line
- Quick detection and guidance
- Fallback for cmd.exe users

**Try this first on Windows!**

---

### `setup.ps1` - PowerShell Alternative

**Features:**
- ✅ Pure PowerShell (no bash required)
- ✅ Color output in PowerShell ISE
- ✅ Virtual environment setup
- ✅ Dependency installation
- ✅ Playwright setup

**Best for:**
- Windows users comfortable with PowerShell
- PowerShell 7+ environments
- CI/CD in Azure environments

**Known limitations:**
- Some features may differ from bash version
- Requires PowerShell 5.0+
- May need execution policy change

---

## 🚀 Quick Start by OS

### **Linux (Ubuntu/Debian/Fedora/CentOS)**

```bash
# Clone repo
git clone <repo-url>
cd agentic_job_finder

# Run setup
bash setup.sh

# Done! Follow on-screen instructions
```

### **macOS**

```bash
# Prerequisites (if needed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.12

# Then same as Linux
bash setup.sh
```

### **Windows - Recommended Path**

```powershell
# Install Git for Windows first
# Download: https://git-scm.com/download/win
# (includes Git Bash)

# Then in Git Bash:
bash setup.sh
```

### **Windows - Alternative 1 (WSL)**

```bash
# In Windows PowerShell (Admin)
wsl --install

# In WSL terminal:
bash setup.sh
```

### **Windows - Alternative 2 (PowerShell only)**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\setup.ps1
```

### **Windows - Alternative 3 (Manual)**

If all else fails:
```cmd
# Install Python 3.12+, Docker, Git manually
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
docker-compose up -d
```

---

## ✅ Platform-Independent Features

Your setup now handles:

| Feature | Linux | macOS | Windows |
|---------|-------|-------|---------|
| ANSI Colors | ✅ | ✅ | ✅ (Git Bash/WSL) |
| Virtual Env | ✅ | ✅ | ✅ |
| Permissions | ✅ | ✅ | ✅ (skipped on Windows) |
| Docker Detection | ✅ | ✅ | ✅ |
| Docker Compose | ✅ | ✅ | ✅ |
| npm Setup | ✅ | ✅ | ✅ |
| Playwright | ✅ | ✅ | ✅ |
| Error Handling | ✅ | ✅ | ✅ |

---

## 🔍 Technical Details

### Operating System Detection

```bash
OS_TYPE=$(uname -s)
case "$OS_TYPE" in
    MINGW64*|MSYS*|CYGWIN*)  # Windows shells
    Darwin)                   # macOS
    Linux)                    # Linux
    *)                        # BSD and others
esac
```

### Color Output

```bash
if [ "$IS_WINDOWS" = true ]; then
    # Plain text (cmd.exe doesn't support ANSI)
    echo "[INFO] Message"
else
    # ANSI colors (Unix-like systems)
    echo -e "${BLUE}[INFO]${NC} Message"
fi
```

### Virtual Environment

```bash
if [ "$IS_WINDOWS" = true ]; then
    source .venv/Scripts/activate  # Windows (Git Bash)
else
    source .venv/bin/activate      # Unix-like
fi
```

### permissions

```bash
if [ "$IS_WINDOWS" = false ]; then
    chmod -R 755 data  # Unix-like only
fi
```

---

## 🆘 Troubleshooting

### "bash: command not found" on Windows

**Solution 1: Install Git Bash**
1. Download [Git for Windows](https://git-scm.com/download/win)
2. Install with default options
3. Open "Git Bash" from Start menu

**Solution 2: Install WSL**
```powershell
# As Administrator
wsl --install
# Restart and run bash setup.sh in WSL terminal
```

### "Permission denied" on macOS

```bash
# Make scripts executable
chmod +x setup.sh setup.bat setup.ps1

# Then run
bash setup.sh
```

### PowerShell execution policy error

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Virtual environment not activating

- Windows: Check `.venv\Scripts\activate.bat` exists
- Unix: Check `.venv/bin/activate` exists
- Recreate: `rm -rf .venv && python3 -m venv .venv`

### Docker not found

```bash
# Install Docker Desktop
# Windows: https://docs.docker.com/docker-for-windows/install/
# macOS: https://docs.docker.com/docker-for-mac/install/
# Linux: https://docs.docker.com/engine/install/
```

---

## 📝 Manual Setup (If Needed)

If scripts fail completely:

### Linux/macOS
```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 3. Setup Playwright
playwright install chromium

# 4. Create directories
mkdir -p data/resumes

# 5. Setup frontend
cd frontend && npm install && cd ..

# 6. Start Docker
docker-compose up -d
```

### Windows (cmd.exe)
```cmd
REM 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate.bat

REM 2. Install dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

REM 3. Setup Playwright
playwright install chromium

REM 4. Create directories
mkdir data\resumes

REM 5. Setup frontend
cd frontend
npm install
cd ..

REM 6. Start Docker
docker-compose up -d
```

---

## 🎉 After Setup

All platforms should show:

```
╔════════════════════════════════════════╗
║   Setup Complete!                      ║
╚════════════════════════════════════════╝

Next steps:
1. Verify all services are running: docker-compose ps
2. Start the backend: source .venv/bin/activate && python api/main.py
3. In another terminal, start the frontend: cd frontend && npm run dev
4. Open browser to http://localhost:3000
```

---

## 📞 Need Help?

1. **Check errors above** - Most issues are listed

2. **Try alternative setup method**
   - Linux: Try bash only
   - Windows: Try Git Bash → WSL → PowerShell

3. **Manual setup**
   - Follow [Manual Setup](#-manual-setup-if-needed) section

4. **Check logs**
   ```bash
   # Docker setup
   docker-compose logs db
   
   # Frontend setup
   cd frontend && npm list
   
   # Backend
   pip list | grep -E "fastapi|sqlalchemy"
   ```

5. **Rebuild everything**
   ```bash
   docker-compose down
   rm -rf .venv node_modules
   bash setup.sh  # or .\setup.ps1 on Windows
   ```

---

## ✨ Features Summary

- ✅ Works on Linux, macOS, Windows
- ✅ Automatic OS detection
- ✅ No manual path configuration
- ✅ Multiple setup methods
- ✅ Clear error messages
- ✅ Color output (where supported)
- ✅ Docker auto-detection
- ✅ Fallback options

**This is production-ready, cross-platform setup!** 🚀

