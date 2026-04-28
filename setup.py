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
from urllib.parse import urlparse

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


def _ask_choice(question: str, choices: dict[str, str]) -> str:
    """Ask user to pick one choice and return the choice key."""
    while True:
        print(f"\n{_c('yellow', question)}")
        for key, label in choices.items():
            print(f"  {key}) {label}")
        ans = input("Select option: ").strip().lower()
        if ans in choices:
            return ans
        print("  Invalid selection. Please choose one of:", ", ".join(choices.keys()))


def _version_of(cmd: str) -> str:
    try:
        r = subprocess.run([cmd, "--version"], capture_output=True, text=True)
        out = (r.stdout or r.stderr or "").strip().splitlines()
        return out[0] if out else "unknown"
    except Exception:
        return "unknown"


def _docker_daemon_available() -> bool:
    """Return True if Docker CLI can talk to the daemon/socket."""
    try:
        _run(["docker", "info"], check=True, capture=True)
        return True
    except Exception:
        return False

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


def step_choose_setup_mode() -> str:
    """Ask user whether to use Docker or local services."""
    header("Step 2.5 · Choose Setup Mode")
    choice = _ask_choice(
        "How do you want to run backend services?",
        {
            "1": "Docker (recommended)",
            "2": "Local services on this machine",
        },
    )
    mode = "docker" if choice == "1" else "local"
    ok(f"Selected setup mode: {mode}")
    return mode


def _read_env_vars(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            data[key] = value
    return data


def _is_placeholder_value(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    placeholder_markers = (
        "your_",
        "replace_",
        "example",
        "changeme",
        "change_me",
        "placeholder",
        "optional_api_key",
    )
    return any(marker in lowered for marker in placeholder_markers)


def step_validate_env(setup_mode: str) -> bool:
    """Validate .env keys and mode-specific connection values. Returns False on validation errors."""
    header("Step 2.6 · Validate Environment")
    env_path = Path(".env")
    example_path = Path(".env.example")

    if not env_path.exists():
        error(".env file is missing")
        print("  Create .env from .env.example first, then re-run setup.py")
        return False

    env_vars = _read_env_vars(env_path)
    example_vars = _read_env_vars(example_path)
    frontend_env_path = Path("frontend/.env")
    frontend_env_local_path = Path("frontend/.env.local")
    frontend_env_vars = _read_env_vars(frontend_env_path)
    if not frontend_env_vars and frontend_env_local_path.exists():
        frontend_env_vars = _read_env_vars(frontend_env_local_path)

    optional_keys = {
        "QDRANT_API_KEY",  # optional for local/default docker Qdrant
        "QDRANT_URL_CLOUD",
        "QDRANT_API_KEY_CLOUD",
        "GROQ_API_KEY",
        "LANGCHAIN_API_KEY",
    }

    frontend_only_keys = {
        "AUTH_SECRET",
        "AUTH_TRUST_HOST",
        "NEXTAUTH_URL",
        "NEXT_PUBLIC_API_URL",
    }

    required_keys = [
        k for k in example_vars.keys()
        if k not in optional_keys and k not in frontend_only_keys
    ]
    frontend_required_keys = ["AUTH_SECRET", "NEXT_PUBLIC_API_URL"]

    missing: list[str] = []
    placeholder: list[str] = []

    for key in required_keys:
        value = env_vars.get(key, "").strip()
        if not value:
            missing.append(key)
            continue
        if _is_placeholder_value(value):
            placeholder.append(key)

    mode_errors: list[str] = []
    frontend_missing: list[str] = []
    frontend_placeholder: list[str] = []
    db_url = env_vars.get("DATABASE_URL", "")
    redis_url = env_vars.get("REDIS_URL", "")
    qdrant_url = env_vars.get("QDRANT_URL", "")

    for key in frontend_required_keys:
        value = frontend_env_vars.get(key, "").strip()
        if not value:
            frontend_missing.append(key)
            continue
        if _is_placeholder_value(value):
            frontend_placeholder.append(key)

    if db_url:
        parsed = urlparse(db_url)
        db_host = parsed.hostname or ""
        if setup_mode == "docker":
            if db_host not in {"db", "localhost", "127.0.0.1"}:
                mode_errors.append(
                    "DATABASE_URL host should be 'db' for docker setup (or localhost for host-run migrations)."
                )
        else:
            if db_host == "db":
                mode_errors.append(
                    "DATABASE_URL in .env uses docker host 'db'."
                )

    if setup_mode == "local":
        if "redis://redis:" in redis_url:
            mode_errors.append("REDIS_URL in .env uses docker host 'redis'.")
        if "http://qdrant:" in qdrant_url:
            mode_errors.append("QDRANT_URL in .env uses docker host 'qdrant'.")

    if not missing and not placeholder and not mode_errors and not frontend_missing and not frontend_placeholder:
        ok("Environment validation passed")
        return True

    error("Environment validation failed. Please fix these issues and re-run setup.py")
    if missing:
        print("\n  Missing keys:")
        for key in missing:
            print(f"    - {key}")
    if placeholder:
        print("\n  Keys still using placeholder/example values:")
        for key in placeholder:
            print(f"    - {key}")

    if frontend_missing or frontend_placeholder:
        print("\n  Frontend environment issues:")
        location = "frontend/.env"
        if not frontend_env_path.exists() and frontend_env_local_path.exists():
            location = "frontend/.env.local"
        if frontend_missing:
            print(f"    File: {location}")
            print("    Missing keys:")
            for key in frontend_missing:
                print(f"      - {key}")
        if frontend_placeholder:
            print(f"    File: {location}")
            print("    Keys still using placeholder/example values:")
            for key in frontend_placeholder:
                print(f"      - {key}")

    if mode_errors:
        print("\n  Setup-mode mismatches:")
        for msg in mode_errors:
            print(f"    - {msg}")

    return False


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
        # _run(["npm", "install"], cwd="frontend")
        npm_cmd = "npm.cmd" if IS_WINDOWS else "npm"
        _run([npm_cmd, "install"], cwd="frontend")
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


def step_docker_services() -> bool:
    """Start Docker services. Returns True when docker services were started."""
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
        return False

    if not _docker_daemon_available():
        error("Docker daemon is not reachable.")
        print("  This is not a compose service naming issue.")
        print("  Fix one of the following and run setup again:")
        if IS_LINUX:
            print("  1) Start daemon: sudo systemctl start docker")
            print("  2) Enable on boot: sudo systemctl enable docker")
            print("  3) Optional non-root access: sudo usermod -aG docker $USER (then re-login)")
            print("  4) Verify: docker info")
        else:
            print("  1) Start Docker Desktop")
            print("  2) Verify: docker info")
        return False

    if _ask("Start Docker services (PostgreSQL, Redis, Qdrant, Celery)?"):
        info("Starting services with docker compose up -d…")
        try:
            _run(compose_cmd + ["up", "-d"])
            ok("Docker services started")
            info("Waiting 10 seconds for services to initialise…")
            import time
            time.sleep(10)
            return True
        except RuntimeError as e:
            error(str(e))
            print("  If you see 'Cannot connect to the Docker daemon', start Docker first:")
            if IS_LINUX:
                print("  sudo systemctl start docker")
            else:
                print("  Start Docker Desktop")
            return False
    else:
        warn("Skipped. Run manually later: docker compose up -d")
        return False


def step_local_services_setup():
    """Guide users through non-Docker local services setup."""
    header("Step 8.5 · Local Services (No Docker)")
    info("Docker was skipped. Configuring for local services on this machine.")
    print("  Recommended for local setup:")
    print("    1) PostgreSQL running on localhost:5432")
    print("    2) Redis running on localhost:6379")
    print("    3) Qdrant running on localhost:6333")

    env_path = Path(".env")
    if env_path.exists():
        lines = env_path.read_text().splitlines()
        db_line = next((ln for ln in lines if ln.startswith("DATABASE_URL=")), "")
        redis_line = next((ln for ln in lines if ln.startswith("REDIS_URL=")), "")
        qdrant_line = next((ln for ln in lines if ln.startswith("QDRANT_URL=")), "")

        if db_line and "@db:" in db_line:
            warn("DATABASE_URL is using docker host 'db'. For local setup use localhost.")
            print("  Example:")
            print("  DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/<db>")
        elif db_line:
            ok("DATABASE_URL looks local-friendly")
        else:
            warn("DATABASE_URL missing in .env")

        if redis_line and "redis://redis:" in redis_line:
            warn("REDIS_URL is using docker host 'redis'. For local setup use localhost.")
            print("  Example: REDIS_URL=redis://localhost:6379/0")
        elif redis_line:
            ok("REDIS_URL looks local-friendly")
        else:
            warn("REDIS_URL missing in .env")

        if qdrant_line and "http://qdrant:" in qdrant_line:
            warn("QDRANT_URL is using docker host 'qdrant'. For local setup use localhost.")
            print("  Example: QDRANT_URL=http://localhost:6333")
        elif qdrant_line:
            ok("QDRANT_URL looks local-friendly")
        else:
            warn("QDRANT_URL missing in .env")

    print("\n  Install/start local services as needed:")
    if IS_LINUX:
        print("    PostgreSQL: sudo apt install postgresql && sudo systemctl start postgresql")
        print("    Redis:      sudo apt install redis-server && sudo systemctl start redis-server")
    elif IS_MACOS:
        print("    PostgreSQL: brew install postgresql@16 && brew services start postgresql@16")
        print("    Redis:      brew install redis && brew services start redis")
    else:
        print("    PostgreSQL: install via official installer and start the service")
        print("    Redis:      use Redis for Windows-compatible setup or WSL")
    print("    Qdrant:     run binary locally or use: docker run -p 6333:6333 qdrant/qdrant")


def step_run_migrations(setup_mode: str):
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

    compose_cmd: list[str] | None = None
    if setup_mode == "docker" and _cmd_exists("docker"):
        try:
            _run(["docker", "compose", "version"], check=True, capture=True)
            compose_cmd = ["docker", "compose"]
        except Exception:
            if _cmd_exists("docker-compose"):
                compose_cmd = ["docker-compose"]

    if _ask("Run database migrations (Alembic)?"):
        if setup_mode == "docker":
            host_db_url = db_url.replace("@db:", "@localhost:")
        else:
            host_db_url = db_url

        env = {**os.environ, "DATABASE_URL": host_db_url, "PYTHONPATH": str(ROOT_DIR)}
        try:
            _run([alembic_cmd, "upgrade", "head"], cwd="db/migrations", env=env)
            ok("Database migrations applied")
        except RuntimeError:
            if setup_mode != "docker":
                error("Local migrations failed — is local PostgreSQL running on localhost?")
                print("  Verify your DATABASE_URL in .env")
                print("  Then run: cd db/migrations && alembic upgrade head")
                return

            warn("Host migration failed. Trying inside Docker API container…")
            if compose_cmd is not None:
                try:
                    _run(compose_cmd + ["exec", "-T", "api", "alembic", "upgrade", "head"])
                    ok("Database migrations applied (inside Docker API container)")
                    return
                except RuntimeError:
                    warn("Docker migration failed. Recreating db/api containers and retrying once…")
                    try:
                        _run(compose_cmd + ["up", "-d", "--force-recreate", "db", "api"])
                        _run(compose_cmd + ["exec", "-T", "api", "alembic", "upgrade", "head"])
                        ok("Database migrations applied after container recreation")
                        return
                    except RuntimeError:
                        pass

            error("Migrations failed — is the database running?")
            print("  Verify: docker compose ps")
            print("  Try host run:   cd db/migrations && alembic upgrade head")
            print("  Try docker run: docker compose exec -T api alembic upgrade head")
    else:
        warn("Skipped. Run manually: cd db/migrations && alembic upgrade head")




def print_summary(setup_mode: str, docker_started: bool):
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
    if setup_mode == "docker":
        if docker_started:
            print(f"    1. Services:         {_c('blue', 'already started via docker compose')}")
        else:
            print(f"    1. Start services:   {_c('blue', 'docker compose up -d')}")
    else:
        print(f"    1. Start services:   {_c('blue', 'start local PostgreSQL/Redis/Qdrant services')}")
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
    setup_mode = step_choose_setup_mode()
    if not step_validate_env(setup_mode):
        sys.exit(1)

    step_setup_venv()
    step_install_dependencies()
    step_setup_playwright()
    step_create_directories()
    step_setup_frontend()
    step_clone_mcp_qdrant()
    docker_started = False
    if setup_mode == "docker":
        docker_started = step_docker_services()
    else:
        step_local_services_setup()

    step_run_migrations(setup_mode)
    print_summary(setup_mode, docker_started)


if __name__ == "__main__":
    main()