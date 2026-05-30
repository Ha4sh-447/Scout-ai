#!/usr/bin/env python3
"""
Initialize database - create all tables and run migrations.
Works with Docker setup via postgresql://db:5432

Usage:
    python scripts/init_db.py
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

from core.console import color_text, print_status

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


load_dotenv()

def run_migrations():
    """Run Alembic migrations"""
    try:
        print_status("RUNNING", "Executing: alembic upgrade head", "blue")
        
        # Change to migrations directory
        migrations_dir = os.path.join(project_root, "db", "migrations")
        if not os.path.exists(migrations_dir):
            print_status("FAILED", f"Migrations directory not found: {migrations_dir}", "red")
            return False
        
        # Run alembic upgrade
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=migrations_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Show output
        if result.stdout:
            print(result.stdout)
        
        if result.returncode == 0:
            print_status("OK", "Database migrations completed successfully", "green")
            return True
        else:
            print_status("FAILED", f"Migration failed with exit code: {result.returncode}", "red")
            if result.stderr:
                print_status("FAILED", f"STDERR: {result.stderr}", "red")
            if result.stdout:
                print_status("FAILED", f"STDOUT: {result.stdout}", "red")
            return False
            
    except FileNotFoundError:
        print_status("FAILED", "Error: 'alembic' command not found", "red")
        print(color_text("   Install with: pip install alembic", "red"))
        return False
    except subprocess.TimeoutExpired:
        print_status("FAILED", "Migration timed out (exceeded 60 seconds)", "red")
        return False
    except Exception as e:
        print_status("FAILED", f"Error running migrations: {type(e).__name__}: {e}", "red")
        return False

def verify_database():
    """Verify database connection using psycopg2 directly to avoid async issues"""
    try:
        import psycopg2
        from urllib.parse import unquote
        import re

        db_url = os.getenv("DATABASE_URL")
        if db_url:
            try:
                # Remove the +asyncpg part
                db_url = db_url.replace("+asyncpg", "")
                
                # Parse: postgresql://user:password@host:port/dbname
                match = re.match(r'postgresql://([^:]+):(.+)@([^:]+):(\d+)/(.+)', db_url)
                if not match:
                    print_status("FAILED", "Invalid DATABASE_URL format", "red")
                    return False
                
                db_user, db_password_encoded, db_host, db_port, db_name = match.groups()
                db_password = unquote(db_password_encoded)  
                db_port = int(db_port)
            except Exception as e:
                print_status("FAILED", f"Failed to parse DATABASE_URL: {e}", "red")
                return False
        else:
            db_user = os.getenv("DB_USER", "")
            db_password = os.getenv("DB_PASSWORD", "")
            db_name = os.getenv("DB_NAME", "")
            db_host = os.getenv("DB_HOST", "db")
            db_port = int(os.getenv("DB_PORT", "5432"))
        
        print_status("CHECK", f"Testing database connection to {db_host}:{db_port}/{db_name} as {db_user}...", "blue")
        
        # Use psycopg2 directly to avoid async complications
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            connect_timeout=5
        )
        conn.close()
        print_status("OK", "Database connection verified", "green")
        return True
            
    except ImportError as e:
        print_status("FAILED", "psycopg2 not found", "red")
        print(color_text(f"   Error: {e}", "red"))
        return False
    except Exception as e:
        # Catch all psycopg2 exceptions here
        print_status("FAILED", f"Database connection failed: {type(e).__name__}: {e}", "red")
        print(color_text("   Troubleshooting:", "red"))
        print(color_text("   1. Check PostgreSQL is running: docker-compose ps db", "red"))
        print(color_text("   2. Verify credentials in .env (DB_USER, DB_PASSWORD, DB_NAME)", "red"))
        print(color_text("   3. Check DATABASE_URL format: postgresql://user:pass@host:port/db", "red"))
        print(color_text("   4. Ensure password is URL-encoded if it contains special characters", "red"))
        return False

def main():
    print("=" * 70)
    print(color_text("DATABASE INITIALIZATION SCRIPT", "blue"))
    print("=" * 70)
    print()
    
    # Check environment
    print_status("INFO", "Checking environment variables...", "blue")
    db_url = os.getenv("DATABASE_URL")
    db_user = os.getenv("DB_USER", "harsh")
    db_name = os.getenv("DB_NAME", "job_agent")
    
    if db_url:
        print(color_text(f"  DATABASE_URL: {db_url[:50]}... (truncated)", "blue"))
    else:
        print(color_text("  DATABASE_URL: Not set (using DB_USER, DB_PASSWORD, DB_NAME)", "blue"))
        print(color_text(f"    DB_USER: {db_user}", "blue"))
        print(color_text(f"    DB_PASSWORD: {'***' if os.getenv('DB_PASSWORD') else '(not set)'}", "blue"))
        print(color_text(f"    DB_NAME: {db_name}", "blue"))
    print()
    
    # Verify connection first
    print_status("STEP 1/2", "Verifying database connection...", "blue")
    if not verify_database():
        print()
        print_status("FAILED", "Could not connect to database. Aborting.", "red")
        sys.exit(1)
    print()
    
    # Run migrations
    print_status("STEP 2/2", "Running database migrations...", "blue")
    if not run_migrations():
        print()
        print_status("FAILED", "Migrations failed. Aborting.", "red")
        sys.exit(1)
    print()
    
    print("=" * 70)
    print_status("SUCCESS", "Database initialization complete!", "green")
    print("=" * 70)

if __name__ == "__main__":
    main()
