#!/bin/bash

# Comprehensive project setup script (Platform Independent)
# This script sets up the entire project environment
# Supports: Linux, macOS, Windows (Git Bash/WSL), BSD

set -e

# Detect OS and setup colors accordingly
OS_TYPE=$(uname -s)
case "$OS_TYPE" in
    MINGW64*|MSYS*|CYGWIN*)
        IS_WINDOWS=true
        ;;
    *)
        IS_WINDOWS=false
        ;;
esac

# Colors for output (safe for all platforms)
if [ "$IS_WINDOWS" = true ]; then
    # Windows doesn't support ANSI colors in cmd.exe, disable them
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
else
    # ANSI colors for Unix-like systems
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
fi

# Logging functions
log_info() {
    if [ -z "$RED" ]; then
        echo "[INFO] $1"
    else
        echo -e "${BLUE}[INFO]${NC} $1"
    fi
}

log_success() {
    if [ -z "$RED" ]; then
        echo "[OK] $1"
    else
        echo -e "${GREEN}[✓]${NC} $1"
    fi
}

log_warning() {
    if [ -z "$RED" ]; then
        echo "[WARNING] $1"
    else
        echo -e "${YELLOW}[WARNING]${NC} $1"
    fi
}

log_error() {
    if [ -z "$RED" ]; then
        echo "[ERROR] $1"
    else
        echo -e "${RED}[ERROR]${NC} $1"
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check prerequisites
step_check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command_exists python3; then
        log_error "Python 3 is not installed"
        exit 1
    fi
    log_success "Python 3 is installed: $(python3 --version)"
    
    if ! command_exists pip; then
        log_error "pip is not installed"
        exit 1
    fi
    log_success "pip is installed"
    
    if ! command_exists docker; then
        log_warning "Docker is not installed. Docker services won't run."
    else
        log_success "Docker is installed: $(docker --version)"
    fi
    
    if ! command_exists docker-compose; then
        log_warning "Docker Compose is not installed. Docker services won't run."
    else
        log_success "Docker Compose is installed: $(docker-compose --version)"
    fi
    
    if ! command_exists git; then
        log_warning "Git is not installed"
    else
        log_success "Git is installed"
    fi
}

# Step 2: Load environment variables
step_setup_env() {
    log_info "Setting up environment variables..."
    
    if [ ! -f ".env" ]; then
        log_warning ".env file not found. Creating from template..."
        if [ -f ".env.example" ]; then
            cp .env.example .env
            log_success ".env file created from .env.example"
        else
            log_warning "No .env.example file found. Please create .env manually with required variables:"
            echo "  - MISTRAL_API_KEY"
            echo "  - DATABASE_URL"
            echo "  - QDRANT_URL"
            echo "  - QDRANT_API_KEY (optional)"
            echo "  - DB_USER"
            echo "  - DB_PASSWORD"
            echo "  - DB_NAME"
        fi
    else
        log_success ".env file exists"
    fi
    
    # Load environment
    if [ -f ".env" ]; then
        set -a
        source .env
        set +a
        log_success "Environment variables loaded"
    fi
}

# Step 3: Create Python virtual environment
step_setup_venv() {
    log_info "Setting up Python virtual environment..."
    
    if [ ! -d ".venv" ]; then
        python3 -m venv .venv
        log_success "Virtual environment created"
    else
        log_success "Virtual environment already exists"
    fi
    
    # Activate virtual environment (platform-aware)
    if [ "$IS_WINDOWS" = true ]; then
        # Windows: Git Bash, WSL, or MSYS
        if [ -f ".venv/Scripts/activate" ]; then
            source .venv/Scripts/activate
        else
            source .venv/bin/activate
        fi
    else
        # Unix-like systems: Linux, macOS, BSD
        source .venv/bin/activate
    fi
    log_success "Virtual environment activated"
}

# Step 4: Install Python dependencies
step_install_dependencies() {
    log_info "Installing Python dependencies..."
    
    pip install --upgrade pip setuptools wheel
    pip install -r requirements.txt
    
    log_success "Python dependencies installed"
}

# Step 5: Install Playwright browsers
step_setup_playwright() {
    log_info "Setting up Playwright browsers..."
    
    playwright install chromium
    
    log_success "Playwright browsers installed"
}

# Step 6: Create required directories
step_create_directories() {
    log_info "Creating required data directories..."
    
    mkdir -p data/resumes
    
    # Set permissions only on Unix-like systems (Windows doesn't support chmod the same way)
    if [ "$IS_WINDOWS" = false ]; then
        chmod -R 755 data
    fi
    
    log_success "Data directories created"
}

# Step 7: Run database migrations
step_run_migrations() {
    log_info "Running database migrations..."
    
    if [ -z "$DATABASE_URL" ]; then
        log_error "DATABASE_URL is not set. Cannot run migrations."
        log_warning "Please set DATABASE_URL in your .env file and run:"
        echo "  cd db/migrations && alembic upgrade head"
        return
    fi
    
    cd db/migrations
    if alembic upgrade head; then
        log_success "Database migrations completed"
    else
        log_error "Database migrations failed"
        log_warning "Make sure PostgreSQL is running and DATABASE_URL is correct"
        cd - > /dev/null
        return
    fi
    cd - > /dev/null
}

# Step 8: Run preflight checks
step_preflight_checks() {
    log_info "Running preflight checks..."
    
    python3 scripts/preflight.py
    
    log_success "Preflight checks completed"
}

# Step 9: Setup frontend
step_setup_frontend() {
    log_info "Setting up frontend..."
    
    if [ ! -d "frontend/node_modules" ]; then
        cd frontend
        if command_exists npm; then
            npm install
            log_success "Frontend dependencies installed"
        else
            log_warning "npm is not installed. Cannot install frontend dependencies"
        fi
        cd - > /dev/null
    else
        log_success "Frontend dependencies already installed"
    fi
}

# Step 10: Start Docker services (optional)
step_docker_setup() {
    log_info "Docker services setup..."
    
    # Try to find docker-compose command (newer versions use "docker compose")
    local docker_compose_cmd="docker-compose"
    if command_exists docker && docker compose version >/dev/null 2>&1; then
        docker_compose_cmd="docker compose"
    fi
    
    if command_exists docker; then
        if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
            read -p "Do you want to start Docker services? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log_info "Starting Docker services..."
                $docker_compose_cmd up -d
                log_success "Docker services started"
                
                # Wait for services to be ready
                log_info "Waiting for services to be ready..."
                sleep 10
                
                # Check if containers are running
                if $docker_compose_cmd ps | grep -q "job_finder_db"; then
                    log_success "PostgreSQL is running"
                fi
                if $docker_compose_cmd ps | grep -q "qdrant"; then
                    log_success "Qdrant is running"
                fi
                if $docker_compose_cmd ps | grep -q "job_finder_redis"; then
                    log_success "Redis is running"
                fi
            fi
        else
            log_warning "Docker Compose is not installed. Skipping Docker services."
        fi
    else
        log_warning "Docker is not installed. Skipping Docker services."
    fi
}

# Main execution
main() {
    if [ "$IS_WINDOWS" = true ]; then
        echo "╔════════════════════════════════════════╗"
        echo "║   Project Setup Script (v2.0)          ║"
        echo "║   Agentic Job Finder                   ║"
        echo "║   Platform-Independent Edition         ║"
        echo "╚════════════════════════════════════════╝"
    else
        echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
        echo -e "${BLUE}║   Project Setup Script (v2.0)          ║${NC}"
        echo -e "${BLUE}║   Agentic Job Finder                   ║${NC}"
        echo -e "${BLUE}║   Platform-Independent Edition         ║${NC}"
        echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    fi
    echo ""
    
    # Go to project root
    cd "$(dirname "$0")"
    
    step_check_prerequisites
    echo ""
    
    step_setup_env
    echo ""
    
    step_setup_venv
    echo ""
    
    step_install_dependencies
    echo ""
    
    step_setup_playwright
    echo ""
    
    step_create_directories
    echo ""
    
    step_setup_frontend
    echo ""
    
    step_run_migrations
    echo ""
    
    step_preflight_checks
    echo ""
    
    step_docker_setup
    echo ""
    
    if [ "$IS_WINDOWS" = true ]; then
        echo "╔════════════════════════════════════════╗"
        echo "║   Setup Complete!                      ║"
        echo "╚════════════════════════════════════════╝"
    else
        echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   Setup Complete!                      ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    fi
    echo ""
    
    if [ "$IS_WINDOWS" = true ]; then
        echo "Next steps:"
    else
        echo -e "${YELLOW}Next steps:${NC}"
    fi
    echo "1. Verify all services are running: docker-compose ps"
    echo "2. Start the backend: source .venv/bin/activate && python api/main.py"
    echo "3. In another terminal, start the frontend: cd frontend && npm run dev"
    echo "4. Open browser to http://localhost:3000"
    echo ""
}

# Run main function
main "$@"
