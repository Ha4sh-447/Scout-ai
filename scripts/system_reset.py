#!/usr/bin/env python3
"""
Complete system reset - clear records from PostgreSQL, Redis and Qdrant.
[WARNING] DESTRUCTIVE - Use with caution! Deletes data records only.

Usage:
    python scripts/system_reset.py              
    python scripts/system_reset.py --force     
    python scripts/system_reset.py --database-only  
    python scripts/system_reset.py --redis-only    
    python scripts/system_reset.py --qdrant-only   
"""

import os
import sys
import argparse
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

load_dotenv()


def _swap_host(url: str, new_host: str) -> str:
    """Return a URL with host replaced while preserving auth, port, path, query."""
    parsed = urlparse(url)
    if not parsed.hostname:
        return url

    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo += f":{parsed.password}"
        userinfo += "@"

    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{userinfo}{new_host}{port}"
    return urlunparse(parsed._replace(netloc=netloc))


def _unique(items):
    seen = set()
    out = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _build_db_url_candidates() -> list[str]:
    """Build sync SQLAlchemy DB URL candidates for both Docker and local shells."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        db_user = os.getenv("DB_USER", "")
        db_password = os.getenv("DB_PASSWORD", "")
        db_name = os.getenv("DB_NAME", "")
        db_host = os.getenv("DB_HOST", "db")
        db_url = f"postgresql://{db_user}:{db_password}@{db_host}:5432/{db_name}"

    # system_reset uses sync engine; asyncpg URL causes greenlet_spawn errors.
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    candidates = [sync_url]
    parsed = urlparse(sync_url)
    if parsed.hostname == "db":
        candidates.extend([_swap_host(sync_url, "localhost"), _swap_host(sync_url, "127.0.0.1")])
    elif parsed.hostname in {"localhost", "127.0.0.1"}:
        candidates.append(_swap_host(sync_url, "db"))

    return _unique(candidates)


def _build_redis_url_candidates() -> list[str]:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    candidates = [redis_url]
    parsed = urlparse(redis_url)
    if parsed.hostname == "redis":
        candidates.extend([_swap_host(redis_url, "localhost"), _swap_host(redis_url, "127.0.0.1")])
    elif parsed.hostname in {"localhost", "127.0.0.1"}:
        candidates.append(_swap_host(redis_url, "redis"))
    return _unique(candidates)


def _build_qdrant_url_candidates() -> list[str]:
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    candidates = [qdrant_url]
    parsed = urlparse(qdrant_url)
    if parsed.hostname == "qdrant":
        candidates.extend([_swap_host(qdrant_url, "localhost"), _swap_host(qdrant_url, "127.0.0.1")])
    elif parsed.hostname in {"localhost", "127.0.0.1"}:
        candidates.append(_swap_host(qdrant_url, "qdrant"))
    return _unique(candidates)

def reset_database(force=False):
    """Clear all rows from all tables while preserving schema."""
    try:
        from sqlalchemy import create_engine, text, inspect

        print("[RESET] Resetting PostgreSQL database...")
        engine = None

        # Try Docker hostnames first, then localhost fallbacks.
        for candidate in _build_db_url_candidates():
            try:
                engine = create_engine(candidate)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print(f"   [OK] Connected using: {candidate}")
                break
            except Exception as e:
                print(f"   [WARN] DB connection failed for {candidate}: {e}")
                if engine is not None:
                    engine.dispose()
                engine = None

        if engine is None:
            print("[FAILED] Database reset failed: Could not connect to PostgreSQL using any configured endpoint")
            return False
        
        # Get list of tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(f"   Found {len(tables)} tables:")
            for table in tables:
                print(f"     - {table}")
            
            if not force:
                confirm = input("\n   [WARNING] Delete all table records? (yes/no): ")
                if confirm.lower() != "yes":
                    print("   Cancelled.")
                    return False
        
        # Truncate all tables and reset identities while preserving schema.
        with engine.begin() as connection:
            for table in reversed(tables):
                connection.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
                print(f"   [OK] Cleared table: {table}")
        
        print("[OK] Database records cleared (schema preserved)")
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"[FAILED] Database reset failed: {e}")
        return False

def reset_redis(force=False):
    """Flush Redis data"""
    try:
        import redis
        
        print("[RESET] Resetting Redis...")

        client = None
        for candidate in _build_redis_url_candidates():
            try:
                test_client = redis.from_url(candidate)
                test_client.ping()
                client = test_client
                print(f"   [OK] Connected using: {candidate}")
                break
            except Exception as e:
                print(f"   [WARN] Redis connection failed for {candidate}: {e}")

        if client is None:
            print("[FAILED] Redis reset failed: Could not connect to Redis using any configured endpoint")
            print("   Make sure Redis is running: docker-compose ps redis")
            return False
        
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
    """Delete all Qdrant points while preserving collection definitions."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client import models
        
        print("[RESET] Resetting Qdrant...")

        client = None
        for candidate in _build_qdrant_url_candidates():
            try:
                test_client = QdrantClient(url=candidate)
                test_client.get_collections()
                client = test_client
                print(f"   [OK] Connected using: {candidate}")
                break
            except Exception as e:
                print(f"   [WARN] Qdrant connection failed for {candidate}: {e}")

        if client is None:
            print("[FAILED] Qdrant reset failed: Could not connect to Qdrant using any configured endpoint")
            print("   Make sure Qdrant is running: docker-compose ps qdrant")
            return False

        collections = client.get_collections().collections
        
        if collections:
            print(f"   Found {len(collections)} collections:")
            for collection in collections:
                print(f"     - {collection.name}")
            
            if not force:
                confirm = input("   [WARNING] Delete all points from all collections? (yes/no): ")
                if confirm.lower() != "yes":
                    print("   Cancelled.")
                    return False
            
            for collection in collections:
                try:
                    # Empty filter matches all points.
                    client.delete(
                        collection_name=collection.name,
                        points_selector=models.Filter(must=[]),
                        wait=True,
                    )
                    print(f"   [OK] Cleared points in collection: {collection.name}")
                except Exception as e:
                    print(f"   [WARN] Could not clear collection {collection.name}: {e}")
                    raise
        
        print("[OK] Qdrant points cleared (collections preserved)")
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
    print("[WARNING] WARNING: This will DELETE all system records!")
    print("   - Database table records (schema preserved)")
    print("   - Redis cache")
    print("   - Qdrant points (collections preserved)")
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
    
   
    if args.database_only:
        results["redis"] = results["qdrant"] = None  
    elif args.redis_only:
        results["database"] = results["qdrant"] = None 
    elif args.qdrant_only:
        results["database"] = results["redis"] = None
    
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
