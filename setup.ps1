# PowerShell setup script for Windows users
# This is an alternative to bash for Windows native development

param(
    [switch]$Help = $false
)

# Display help
function Show-Help {
    Write-Host "Project Setup Script - PowerShell Edition" -ForegroundColor Cyan
    Write-Host "Usage: .\setup.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Note: This script requires bash for full functionality." -ForegroundColor Yellow
    Write-Host "For best results, use: bash setup.sh" -ForegroundColor Yellow
}

if ($Help) {
    Show-Help
    exit 0
}

# Color codes (PowerShell compatible)
$Cyan = "Cyan"
$Green = "Green"
$Yellow = "Yellow"
$Red = "Red"

# Script output functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO]" -ForegroundColor $Cyan -NoNewline
    Write-Host " $Message"
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK]" -ForegroundColor $Green -NoNewline
    Write-Host " $Message"
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING]" -ForegroundColor $Yellow -NoNewline
    Write-Host " $Message"
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR]" -ForegroundColor $Red -NoNewline
    Write-Host " $Message"
}

# Check if command exists
function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# Main setup logic
function Initialize-Project {
    Write-Host "╔════════════════════════════════════════╗" -ForegroundColor $Cyan
    Write-Host "║   Project Setup (PowerShell Edition)   ║" -ForegroundColor $Cyan
    Write-Host "║   Agentic Job Finder                   ║" -ForegroundColor $Cyan
    Write-Host "╚════════════════════════════════════════╝" -ForegroundColor $Cyan
    Write-Host ""

    # Step 1: Check prerequisites
    Write-Info "Checking prerequisites..."
    
    if (-not (Test-Command python)) {
        Write-Error "Python is not installed or not in PATH"
        Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
        exit 1
    }
    $pythonVersion = & python --version 2>&1
    Write-Success "Python is installed: $pythonVersion"

    if (-not (Test-Command pip)) {
        Write-Error "pip is not installed"
        exit 1
    }
    Write-Success "pip is installed"

    if (-not (Test-Command docker)) {
        Write-Warning "Docker is not installed (optional for local development)"
    } else {
        $dockerVersion = & docker --version
        Write-Success "Docker is installed: $dockerVersion"
    }
    
    Write-Host ""

    # Step 2: Setup environment file
    Write-Info "Setting up environment variables..."
    
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-Success ".env file created from .env.example"
        } else {
            Write-Warning "No .env.example found. Creating blank .env"
            $null | Out-File -FilePath ".env" -Encoding UTF8
        }
    } else {
        Write-Success ".env file exists"
    }
    Write-Host ""

    # Step 3: Create virtual environment
    Write-Info "Setting up Python virtual environment..."
    
    if (-not (Test-Path ".venv")) {
        & python -m venv .venv
        Write-Success "Virtual environment created"
    } else {
        Write-Success "Virtual environment already exists"
    }

    # Activate venv
    $activateScript = ".\.venv\Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        & $activateScript
        Write-Success "Virtual environment activated"
    } else {
        Write-Error "Could not find venv activation script"
        exit 1
    }
    Write-Host ""

    # Step 4: Install dependencies
    Write-Info "Installing Python dependencies..."
    & pip install --upgrade pip setuptools wheel | Out-Null
    & pip install -r requirements.txt | Out-Null
    Write-Success "Python dependencies installed"
    Write-Host ""

    # Step 5: Install Playwright
    Write-Info "Setting up Playwright browsers..."
    & playwright install chromium | Out-Null
    Write-Success "Playwright browsers installed"
    Write-Host ""

    # Step 6: Create directories
    Write-Info "Creating required directories..."
    if (-not (Test-Path "data/resumes")) {
        $null = New-Item -ItemType Directory -Path "data/resumes" -Force
    }
    Write-Success "Data directories created"
    Write-Host ""

    # Step 7: Setup frontend
    Write-Info "Setting up frontend..."
    if (-not (Test-Path "frontend/node_modules")) {
        if (Test-Command npm) {
            Push-Location frontend
            & npm install | Out-Null
            Pop-Location
            Write-Success "Frontend dependencies installed"
        } else {
            Write-Warning "npm is not installed. Cannot setup frontend."
            Write-Host "Install Node.js from: https://nodejs.org/" -ForegroundColor Yellow
        }
    } else {
        Write-Success "Frontend dependencies already exist"
    }
    Write-Host ""

    # Step 8: Docker setup
    if (Test-Command docker) {
        Write-Info "Docker services available"
        $response = Read-Host "Do you want to start Docker services? (y/n)"
        if ($response -eq 'y' -or $response -eq 'Y') {
            Write-Info "Starting Docker services..."
            & docker-compose up -d
            Write-Success "Docker services started"
            Start-Sleep -Seconds 10
            Write-Info "Services may still be initializing..."
        }
    }
    Write-Host ""

    # Success message
    Write-Host "╔════════════════════════════════════════╗" -ForegroundColor $Green
    Write-Host "║   Setup Complete!                      ║" -ForegroundColor $Green
    Write-Host "╚════════════════════════════════════════╝" -ForegroundColor $Green
    Write-Host ""

    Write-Host "Next steps:" -ForegroundColor $Yellow
    Write-Host "1. Verify services: docker-compose ps"
    Write-Host "2. Start backend: python api/main.py"
    Write-Host "3. Start frontend: cd frontend && npm run dev"
    Write-Host "4. Open: http://localhost:3000"
}

# Run setup
try {
    Initialize-Project
} catch {
    Write-Error "Setup failed: $_"
    exit 1
}
