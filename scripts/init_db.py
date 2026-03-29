#!/usr/bin/env python3
"""
Initialize database - create all tables and run migrations.
Works with Docker setup via postgresql://db:5432

Usage:
    python scripts/init_db.py              # Run Alembic migrations
"""

import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

def run_migrations():
    """Run Alembic migrations"""
    try:
        print("[RUNNING] Running database migrations...")
        
        # Change to project root
        os.chdir(project_root)
        
        # Run alembic upgrade
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print("[OK] Database migrations completed successfully")
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print("[FAILED] Migration failed")
            if result.stderr:
                print(result.stderr)
            return False
            
    except FileNotFoundError:
        print("[FAILED] Error: alembic not found")
        print("   Install with: pip install alembic")
        return False
    except Exception as e:
        print(f"[FAILED] Error running migrations: {e}")
        return False

def verify_database():
    """Verify database connection"""
    try:
        from sqlalchemy import create_engine, text
        
        # Get database URL from environment or use Docker default
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            db_user = os.getenv("DB_USER", "harsh")
            db_password = os.getenv("DB_PASSWORD", "")
            db_name = os.getenv("DB_NAME", "job_agent")
            # Use Docker service name 'db' instead of localhost
            db_url = f"postgresql://{db_user}:{db_password}@db:5432/{db_name}"
        
        print(f"[CHECK] Testing database connection...")
        engine = create_engine(db_url)
        
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("[OK] Database connection verified")
            return True
            
    except Exception as e:
        print(f"[FAILED] Database connection failed: {e}")
        print(f"   Make sure:")
        print(f"   1. PostgreSQL is running: docker-compose ps db")
        print(f"   2. Database credentials are correct in .env")
        print(f"   3. DATABASE_URL or DB_* variables are set")
        return False

def main():
    print("=" * 60)
    print("Database Initialization")
    print("=" * 60)
    
    # Verify connection first
    if not verify_database():
        sys.exit(1)
    
    # Run migrations
    if not run_migrations():
        sys.exit(1)
    
    print("\n[OK] Database initialization complete!")
    print("   Tables created successfully")

if __name__ == "__main__":
    main()
