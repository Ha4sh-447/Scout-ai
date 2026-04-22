#!/usr/bin/env python3
"""
Universal setup script for Agentic Job Finder.
Works on Linux, macOS, and Windows — no bash required.

Usage:
    python setup.py
    python setup.py --check-only # Only check prerequisites
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import colorama
    colorama.init(autoreset=True)
    C = {
        "blue":   colorama.Fore.BLUE,
        "green":  colorama.Fore.GREEN,
        "yellow": colorama.Fore.YELLOW,
        "red":    colorama.Fore.RED,
        "reset":  colorama.Style.RESET_ALL,
    }
except ImportError:
    C = {k: "" for k in ("blue", "green", "yellow", "red", "reset")}


def _c(color: str, text: str) -> str:
    return f"{C[color]}{text}{C['reset']}"


def info(msg: str):    print(_c("blue",   f"[INFO]    {msg}"))
def ok(msg: str):      print(_c("green",  f"[  OK  ]  {msg}"))
def warn(msg: str):    print(_c("yellow", f"[ WARN ]  {msg}"))
def error(msg: str):   print(_c("red",    f"[ERROR]   {msg}"))
def header(msg: str):  print(_c("blue",   f"\n{'─'*50}\n  {msg}\n{'─'*50}"))

IS_WINDOWS = platform.system() == "Windows"
IS_MACOS   = platform.system() == "Darwin"
IS_LINUX   = platform.system() == "Linux"

PYTHON      = sys.executable
PIP         = [PYTHON, "-m", "pip"]
ROOT_DIR    = Path(__file__).parent.resolve()
VENV_BIN    = ROOT_DIR / ".venv" / ("Scripts" if IS_WINDOWS else "bin")
VENV_PYTHON = str(VENV_BIN / ("python.exe" if IS_WINDOWS else "python"))
VENV_PIP    = [VENV_PYTHON, "-m", "pip"]

def _run(cmd: list[str], cwd: str | None = None, env: dict | None = None, check: bool = True, capture: bool = False):
    """Run a subprocess, streaming output unless capture=True."""
    kwargs: dict = {"cwd": cwd, "env": env}
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    result = subprocess.run(cmd, **kwargs)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command {' '.join(cmd)!r} failed with code {result.returncode}")
    return result


def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _ask(question: str) -> bool:
    """Ask a yes/no question. Returns True for yes."""
    while True:
        ans = input(f"\n{_c('yellow', question)} [y/n]: ").strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  Please enter y or n.")


def _version_of(cmd: str) -> str:
    try:
        r = subprocess.run([cmd, "--version"], capture_output=True, text=True)
        out = (r.stdout or r.stderr or "").strip().splitlines()
        return out[0] if out else "unknown"
    except Exception:
        return "unknown"

def step_check_prerequisites() -> bool:
    """Check required and optional tools. Returns False if required tools are missing."""
    header("Step 1 · Checking Prerequisites")
    all_ok = True

    for tool in ("python3" if not IS_WINDOWS else "python", "pip"):
        cmd = tool if _cmd_exists(tool) else ("python" if tool == "python3" else None)
        found = cmd and _cmd_exists(cmd)
        if found:
            ok(f"{tool}: {_version_of(tool)}")
        else:
            error(f"{tool} is not installed or not in PATH")
            if tool.startswith("python"):
                print("  → Download: https://www.python.org/downloads/")
            all_ok = False

    optional = {"git": "https://git-scm.com/downloads"}
    for tool, url in optional.items():
        if _cmd_exists(tool):
            ok(f"{tool}: {_version_of(tool)}")
        else:
            warn(f"{tool} not found — install from {url}")

    docker_ok = _cmd_exists("docker")
    if docker_ok:
        ok(f"docker: {_version_of('docker')}")
    else:
        warn("docker not found — Docker services won't start automatically.")
        print("  → Install Docker Desktop: https://www.docker.com/products/docker-desktop")

    compose_ok = False
    if docker_ok:
        try:
            _run(["docker", "compose", "version"], check=True, capture=True)
            compose_ok = True
            ok("docker compose: available (plugin)")
        except Exception:
            if _cmd_exists("docker-compose"):
                compose_ok = True
                ok("docker-compose: available (standalone)")
            else:
                warn("docker compose not found — Docker services will be skipped")

    npm_ok = _cmd_exists("npm")
    if npm_ok:
        ok(f"node: {_version_of('node')}  |  npm: {_version_of('npm')}")
    else:
        warn("npm not found — frontend deps won't be installed automatically")
        print("  → Install Node.js: https://nodejs.org/")

    print()
    return all_ok


def step_setup_env():
    """Copy .env.example → .env if missing."""
    header("Step 2 · Environment Variables")
    env_path = Path(".env")
    example_path = Path(".env.example")

    if env_path.exists():
        ok(".env already exists")
    elif example_path.exists():
        shutil.copy(example_path, env_path)
        ok(".env created from .env.example")
        warn("Edit .env and fill in your API keys before starting the application!")
    else:
        warn(".env.example not found — you will need to create .env manually")
        print("  Required variables: MISTRAL_API_KEY, JWT_SECRET_KEY, DATABASE_URL,")
        print("  QDRANT_URL, REDIS_URL, CELERY_BROKER_URL, EMAIL_SENDER, EMAIL_PASSWORD")


def step_setup_venv():
    """Create .venv and install dependencies."""
    header("Step 3 · Python Virtual Environment")
    venv_path = Path(".venv")

    if venv_path.exists():
        ok(".venv already exists")
    else:
        info("Creating virtual environment…")
        _run([PYTHON, "-m", "venv", ".venv"])
        ok(".venv created")

    if Path(VENV_PYTHON).exists():
        ok(f"Virtual environment ready at {VENV_BIN}")
    else:
        warn(f"Could not confirm venv at {VENV_PYTHON} — proceeding anyway")


def step_install_dependencies():
    """Upgrade pip and install from requirements.txt."""
    header("Step 4 · Python Dependencies")
    info("Upgrading pip, setuptools, wheel…")
    _run(VENV_PIP + ["install", "--upgrade", "pip", "setuptools", "wheel"])
    info("Installing from requirements.txt…")
    _run(VENV_PIP + ["install", "-r", "requirements.txt"])
    ok("Python dependencies installed")


def step_setup_playwright():
    """Install Playwright Chromium browser."""
    header("Step 5 · Playwright Browsers")
    playwright = str(VENV_BIN / ("playwright.exe" if IS_WINDOWS else "playwright"))
    if not Path(playwright).exists():
        playwright = "playwright"

    if _ask("Install Playwright Chromium browser? (needed for web scraping)"):
        info("Installing Chromium…")
        _run([playwright, "install", "chromium"])
        ok("Playwright Chromium installed")
    else:
        warn("Skipped. Run manually later: playwright install chromium")


def step_create_directories():
    """Create required data directories."""
    header("Step 6 · Data Directories")
    Path("data/resumes").mkdir(parents=True, exist_ok=True)
    ok("data/resumes/ created")


def step_setup_frontend():
    """Install frontend npm dependencies."""
    header("Step 7 · Frontend Dependencies")
    frontend_modules = Path("frontend/node_modules")

    if frontend_modules.exists():
        ok("frontend/node_modules already present")
        return

    if not _cmd_exists("npm"):
        warn("npm not found — skipping frontend setup")
        return

    if _ask("Install frontend npm dependencies? (Node.js/npm)"):
        info("Running npm install in frontend/…")
        _run(["npm", "install"], cwd="frontend")
        ok("Frontend dependencies installed")
    else:
        warn("Skipped. Run manually later: cd frontend && npm install")


def step_clone_mcp_qdrant():
    """Clone the Qdrant MCP server repository if missing."""
    header("Step 7.5 · Qdrant MCP Server")
    qdrant_mcp_path = Path("mcp-server-qdrant")
    if qdrant_mcp_path.exists():
        ok("mcp-server-qdrant already exists")
        return
    if not _cmd_exists("git"):
        warn("git not found — cannot clone mcp-server-qdrant")
        return
    if _ask("Clone mcp-server-qdrant repository?"):
        info("Cloning mcp-server-qdrant…")
        _run(["git", "clone", "https://github.com/qdrant/mcp-server-qdrant.git"])
        ok("mcp-server-qdrant cloned")


def step_docker_services():
    """Start Docker services."""
    header("Step 8 · Docker Services")

    compose_cmd: list[str] | None = None
    if _cmd_exists("docker"):
        try:
            _run(["docker", "compose", "version"], check=True, capture=True)
            compose_cmd = ["docker", "compose"]
        except Exception:
            if _cmd_exists("docker-compose"):
                compose_cmd = ["docker-compose"]

    if compose_cmd is None:
        warn("Docker Compose not found — skipping service startup")
        return

    if _ask("Start Docker services (PostgreSQL, Redis, Qdrant, Celery)?"):
        info("Starting services with docker compose up -d…")
        _run(compose_cmd + ["up", "-d"])
        ok("Docker services started")
        info("Waiting 10 seconds for services to initialise…")
        import time; time.sleep(10)
    else:
        warn("Skipped. Run manually later: docker compose up -d")


def step_run_migrations():
    """Run Alembic database migrations."""
    header("Step 9 · Database Migrations")

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url and Path(".env").exists():
        for line in Path(".env").read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                db_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

    if not db_url:
        warn("DATABASE_URL not set — skipping migrations")
        print("  Run manually later:")
        print("  cd db/migrations && alembic upgrade head")
        return

    alembic = VENV_BIN / ("alembic.exe" if IS_WINDOWS else "alembic")
    if not alembic.exists():
        alembic_cmd = "alembic"
    else:
        alembic_cmd = str(alembic)

    if _ask("Run database migrations (Alembic)?"):
        host_db_url = db_url.replace("@db:", "@localhost:")
        env = {**os.environ, "DATABASE_URL": host_db_url, "PYTHONPATH": str(ROOT_DIR)}
        try:
            _run([alembic_cmd, "upgrade", "head"], cwd="db/migrations", env=env)
            ok("Database migrations applied")
        except RuntimeError:
            error("Migrations failed — is the database running?")
            print("  Verify: docker compose ps")
            print("  Then run: cd db/migrations && alembic upgrade head")
    else:
        warn("Skipped. Run manually: cd db/migrations && alembic upgrade head")




def print_summary():
    activate = (
        r".venv\Scripts\activate" if IS_WINDOWS else "source .venv/bin/activate"
    )
    print()
    width = 46
    print()
    print(_c("green", f"╔{'═'*width}╗"))
    label = "✅  Setup Complete!"
    padding = (width - (len(label) + 1)) // 2
    print(_c("green", f"║{' '*padding}{label}{' '*(width - 19 - padding)}║"))
    print(_c("green", f"╚{'═'*width}╝"))
    print()
    print(_c("yellow", "  Next steps:"))
    print(f"    1. Start services:   {_c('blue', 'docker compose up -d')}")
    print(f"    2. Activate venv:    {_c('blue', activate)}")
    print(f"    3. Start frontend:   {_c('blue', 'cd frontend && npm run dev')}")
    print(f"    4. Access dashboard: {_c('blue', 'http://localhost:3000')}")
    print()
    print()

def main():
    parser = argparse.ArgumentParser(description="Agentic Job Finder — Universal Setup")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check prerequisites without installing anything",
    )
    args = parser.parse_args()

    os.chdir(Path(__file__).parent)

    print()
    width = 46
    print()
    print(_c("blue", f"╔{'═'*width}╗"))
    print(_c("blue", f"║{'Agentic Job Finder — Setup'.center(width)}║"))
    print(_c("blue", f"║{'─'*width}║"))
    print(_c("blue", f"║  Platform: {platform.system():<{width-12}}║"))
    print(_c("blue", f"║  Python:   {sys.version.split()[0]:<{width-12}}║"))
    print(_c("blue", f"╚{'═'*width}╝"))
    print()

    if args.check_only:
        ok_flag = step_check_prerequisites()
        sys.exit(0 if ok_flag else 1)

    prereq_ok = step_check_prerequisites()
    if not prereq_ok:
        error("Required tools are missing. Please install them and re-run setup.py.")
        sys.exit(1)

    step_setup_env()
    step_setup_venv()
    step_install_dependencies()
    step_setup_playwright()
    step_create_directories()
    step_setup_frontend()
    step_clone_mcp_qdrant()
    step_docker_services()
    step_run_migrations()
    print_summary()


if __name__ == "__main__":
    main()