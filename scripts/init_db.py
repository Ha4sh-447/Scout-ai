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

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


load_dotenv()

def run_migrations():
    """Run Alembic migrations"""
    try:
        print("\n[RUNNING] Executing: alembic upgrade head")
        
        # Change to migrations directory
        migrations_dir = os.path.join(project_root, "db", "migrations")
        if not os.path.exists(migrations_dir):
            print(f"[FAILED] Migrations directory not found: {migrations_dir}")
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
            print("[OK] ✓ Database migrations completed successfully")
            return True
        else:
            print("\n[FAILED] Migration failed with exit code:", result.returncode)
            if result.stderr:
                print("STDERR:", result.stderr)
            if result.stdout:
                print("STDOUT:", result.stdout)
            return False
            
    except FileNotFoundError:
        print("[FAILED] Error: 'alembic' command not found")
        print("   Install with: pip install alembic")
        return False
    except subprocess.TimeoutExpired:
        print("[FAILED] Migration timed out (exceeded 60 seconds)")
        return False
    except Exception as e:
        print(f"[FAILED] Error running migrations: {type(e).__name__}: {e}")
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
                    print("[FAILED] Invalid DATABASE_URL format")
                    return False
                
                db_user, db_password_encoded, db_host, db_port, db_name = match.groups()
                db_password = unquote(db_password_encoded)  
                db_port = int(db_port)
            except Exception as e:
                print(f"[FAILED] Failed to parse DATABASE_URL: {e}")
                return False
        else:
            db_user = os.getenv("DB_USER", "")
            db_password = os.getenv("DB_PASSWORD", "")
            db_name = os.getenv("DB_NAME", "")
            db_host = os.getenv("DB_HOST", "db")
            db_port = int(os.getenv("DB_PORT", "5432"))
        
        print(f"[CHECK] Testing database connection to {db_host}:{db_port}/{db_name} as {db_user}...")
        
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
        print("[OK] ✓ Database connection verified")
        return True
            
    except ImportError as e:
        print("[FAILED] psycopg2 not found")
        print(f"   Error: {e}")
        return False
    except Exception as e:
        # Catch all psycopg2 exceptions here
        print(f"[FAILED] Database connection failed: {type(e).__name__}: {e}")
        print(f"   Troubleshooting:")
        print(f"   1. Check PostgreSQL is running: docker-compose ps db")
        print(f"   2. Verify credentials in .env (DB_USER, DB_PASSWORD, DB_NAME)")
        print(f"   3. Check DATABASE_URL format: postgresql://user:pass@host:port/db")
        print(f"   4. Ensure password is URL-encoded if it contains special characters")
        return False

def main():
    print("=" * 70)
    print("DATABASE INITIALIZATION SCRIPT")
    print("=" * 70)
    print()
    
    # Check environment
    print("[INFO] Checking environment variables...")
    db_url = os.getenv("DATABASE_URL")
    db_user = os.getenv("DB_USER", "harsh")
    db_name = os.getenv("DB_NAME", "job_agent")
    
    if db_url:
        print(f"  DATABASE_URL: {db_url[:50]}... (truncated)")
    else:
        print(f"  DATABASE_URL: Not set (using DB_USER, DB_PASSWORD, DB_NAME)")
        print(f"    DB_USER: {db_user}")
        print(f"    DB_PASSWORD: {'***' if os.getenv('DB_PASSWORD') else '(not set)'}")
        print(f"    DB_NAME: {db_name}")
    print()
    
    # Verify connection first
    print("[STEP 1/2] Verifying database connection...")
    if not verify_database():
        print()
        print("[FAILED] Could not connect to database. Aborting.")
        sys.exit(1)
    print()
    
    # Run migrations
    print("[STEP 2/2] Running database migrations...")
    if not run_migrations():
        print()
        print("[FAILED] Migrations failed. Aborting.")
        sys.exit(1)
    print()
    
    print("=" * 70)
    print("[SUCCESS] Database initialization complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
