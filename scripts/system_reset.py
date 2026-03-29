#!/usr/bin/env python3
"""
Complete system reset - drop all tables, clear Redis and Qdrant.
[WARNING] DESTRUCTIVE - Use with caution! Deletes all data.

Usage:
    python scripts/system_reset.py              # Interactive (asks for confirmation)
    python scripts/system_reset.py --force      # Force reset without confirmation
    python scripts/system_reset.py --database-only  # Reset only database
    python scripts/system_reset.py --redis-only     # Reset only Redis
    python scripts/system_reset.py --qdrant-only    # Reset only Qdrant
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

def reset_database(force=False):
    """Drop all tables and recreate them"""
    try:
        from sqlalchemy import create_engine, text, inspect
        
        # Get database URL
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            db_user = os.getenv("DB_USER", "harsh")
            db_password = os.getenv("DB_PASSWORD", "")
            db_name = os.getenv("DB_NAME", "job_agent")
            db_url = f"postgresql://{db_user}:{db_password}@db:5432/{db_name}"
        
        print("[RESET] Resetting PostgreSQL database...")
        engine = create_engine(db_url)
        
        # Get list of tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(f"   Found {len(tables)} tables:")
            for table in tables:
                print(f"     - {table}")
            
            if not force:
                confirm = input("\n   [WARNING] Drop all tables? (yes/no): ")
                if confirm.lower() != "yes":
                    print("   Cancelled.")
                    return False
        
        # Drop all tables
        with engine.begin() as connection:
            for table in reversed(tables):  # Reverse to respect foreign keys
                connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                print(f"   [OK] Dropped table: {table}")
        
        print("[OK] Database reset complete")
        return True
        
    except Exception as e:
        print(f"[FAILED] Database reset failed: {e}")
        return False

def reset_redis(force=False):
    """Flush Redis data"""
    try:
        import redis
        
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        print("[RESET] Resetting Redis...")
        
        client = redis.from_url(redis_url)
        
        # Check Redis connection
        client.ping()
        
        # Get DB size
        db_size = client.dbsize()
        print(f"   Found {db_size} keys in Redis")
        
        if db_size > 0:
            if not force:
                confirm = input("   [WARNING] Flush all Redis data? (yes/no): ")
                if confirm.lower() != "yes":
                    print("   Cancelled.")
                    return False
            
            client.flushdb()
            print("   [OK] Redis flushed")
        
        print("[OK] Redis reset complete")
        return True
        
    except Exception as e:
        print(f"[FAILED] Redis reset failed: {e}")
        print(f"   Make sure Redis is running: docker-compose ps redis")
        return False

def reset_qdrant(force=False):
    """Delete all Qdrant collections"""
    try:
        from qdrant_client import QdrantClient
        
        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        print("[RESET] Resetting Qdrant...")
        
        client = QdrantClient(url=qdrant_url)
        collections = client.get_collections().collections
        
        if collections:
            print(f"   Found {len(collections)} collections:")
            for collection in collections:
                print(f"     - {collection.name}")
            
            if not force:
                confirm = input("   [WARNING] Delete all collections? (yes/no): ")
                if confirm.lower() != "yes":
                    print("   Cancelled.")
                    return False
            
            for collection in collections:
                client.delete_collection(collection.name)
                print(f"   [OK] Deleted collection: {collection.name}")
        
        print("[OK] Qdrant reset complete")
        return True
        
    except Exception as e:
        print(f"[FAILED] Qdrant reset failed: {e}")
        print(f"   Make sure Qdrant is running: docker-compose ps qdrant")
        return False

def main():
    parser = argparse.ArgumentParser(description="Reset system data ([WARNING] DESTRUCTIVE)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--database-only", action="store_true", help="Reset only database")
    parser.add_argument("--redis-only", action="store_true", help="Reset only Redis")
    parser.add_argument("--qdrant-only", action="store_true", help="Reset only Qdrant")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("SYSTEM RESET")
    print("=" * 60)
    print("[WARNING] WARNING: This will DELETE all system data!")
    print("   - Database tables")
    print("   - Redis cache")
    print("   - Qdrant collections")
    print("="*60)
    
    if not args.force:
        confirm = input("\n[CONFIRM] Are you SURE? (type 'reset' to confirm): ")
        if confirm != "reset":
            print("Cancelled.")
            sys.exit(0)
    
    results = {
        "database": True,
        "redis": True,
        "qdrant": True,
    }
    
    # Determine what to reset
    if args.database_only:
        results["redis"] = results["qdrant"] = None  # Skip
    elif args.redis_only:
        results["database"] = results["qdrant"] = None  # Skip
    elif args.qdrant_only:
        results["database"] = results["redis"] = None  # Skip
    
    # Execute resets
    print()
    if results["database"] is not None:
        results["database"] = reset_database(force=args.force)
        print()
    
    if results["redis"] is not None:
        results["redis"] = reset_redis(force=args.force)
        print()
    
    if results["qdrant"] is not None:
        results["qdrant"] = reset_qdrant(force=args.force)
        print()
    
    # Summary
    print("=" * 60)
    print("RESET SUMMARY")
    print("=" * 60)
    if results["database"] is not None:
        status = "[OK]" if results["database"] else "[FAILED]"
        print(f"Database:  {status}")
    if results["redis"] is not None:
        status = "[OK]" if results["redis"] else "[FAILED]"
        print(f"Redis:     {status}")
    if results["qdrant"] is not None:
        status = "[OK]" if results["qdrant"] else "[FAILED]"
        print(f"Qdrant:    {status}")
    print("=" * 60)
    
    # Check overall success
    all_success = all(v for v in results.values() if v is not None)
    if all_success:
        print("\n[OK] System reset complete!")
        print("   Now run: python scripts/init_db.py")
        sys.exit(0)
    else:
        print("\n❌ Some resets failed. Check errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
