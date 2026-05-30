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

from core.console import color_text, print_status

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

        print_status("RESET", "Resetting PostgreSQL database...", "blue")
        engine = None

        # Try Docker hostnames first, then localhost fallbacks.
        for candidate in _build_db_url_candidates():
            try:
                engine = create_engine(candidate)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print_status("OK", f"Connected using: {candidate}", "green")
                break
            except Exception as e:
                print_status("WARN", f"DB connection failed for {candidate}: {e}", "yellow")
                if engine is not None:
                    engine.dispose()
                engine = None

        if engine is None:
            print_status("FAILED", "Database reset failed: Could not connect to PostgreSQL using any configured endpoint", "red")
            return False
        
        # Get list of tables
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        if tables:
            print(color_text(f"   Found {len(tables)} tables:", "blue"))
            for table in tables:
                print(color_text(f"     - {table}", "blue"))
            
            if not force:
                confirm = input(color_text("\n   [WARNING] Delete all table records? (yes/no): ", "yellow"))
                if confirm.lower() != "yes":
                    print(color_text("   Cancelled.", "yellow"))
                    return False
        
        # Truncate all tables and reset identities while preserving schema.
        with engine.begin() as connection:
            for table in reversed(tables):
                connection.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
                print_status("OK", f"Cleared table: {table}", "green")
        
        print_status("OK", "Database records cleared (schema preserved)", "green")
        engine.dispose()
        return True
        
    except Exception as e:
        print_status("FAILED", f"Database reset failed: {e}", "red")
        return False

def reset_redis(force=False):
    """Flush Redis data"""
    try:
        import redis
        
        print_status("RESET", "Resetting Redis...", "blue")

        client = None
        for candidate in _build_redis_url_candidates():
            try:
                test_client = redis.from_url(candidate)
                test_client.ping()
                client = test_client
                print_status("OK", f"Connected using: {candidate}", "green")
                break
            except Exception as e:
                print_status("WARN", f"Redis connection failed for {candidate}: {e}", "yellow")

        if client is None:
            print_status("FAILED", "Redis reset failed: Could not connect to Redis using any configured endpoint", "red")
            print(color_text("   Make sure Redis is running: docker-compose ps redis", "red"))
            return False
        
        # Get DB size
        db_size = client.dbsize()
        print(color_text(f"   Found {db_size} keys in Redis", "blue"))
        
        if db_size > 0:
            if not force:
                confirm = input(color_text("   [WARNING] Flush all Redis data? (yes/no): ", "yellow"))
                if confirm.lower() != "yes":
                    print(color_text("   Cancelled.", "yellow"))
                    return False
            
            client.flushdb()
            print_status("OK", "Redis flushed", "green")
        
        print_status("OK", "Redis reset complete", "green")
        return True
        
    except Exception as e:
        print_status("FAILED", f"Redis reset failed: {e}", "red")
        print(color_text("   Make sure Redis is running: docker-compose ps redis", "red"))
        return False

def reset_qdrant(force=False):
    """Delete all Qdrant points while preserving collection definitions."""
    try:
        from qdrant_client import QdrantClient
        from qdrant_client import models
        
        print_status("RESET", "Resetting Qdrant...", "blue")

        client = None
        for candidate in _build_qdrant_url_candidates():
            try:
                test_client = QdrantClient(url=candidate)
                test_client.get_collections()
                client = test_client
                print_status("OK", f"Connected using: {candidate}", "green")
                break
            except Exception as e:
                print_status("WARN", f"Qdrant connection failed for {candidate}: {e}", "yellow")

        if client is None:
            print_status("FAILED", "Qdrant reset failed: Could not connect to Qdrant using any configured endpoint", "red")
            print(color_text("   Make sure Qdrant is running: docker-compose ps qdrant", "red"))
            return False

        collections = client.get_collections().collections
        
        if collections:
            print(color_text(f"   Found {len(collections)} collections:", "blue"))
            for collection in collections:
                print(color_text(f"     - {collection.name}", "blue"))
            
            if not force:
                confirm = input(color_text("   [WARNING] Delete all points from all collections? (yes/no): ", "yellow"))
                if confirm.lower() != "yes":
                    print(color_text("   Cancelled.", "yellow"))
                    return False
            
            for collection in collections:
                try:
                    # Empty filter matches all points.
                    client.delete(
                        collection_name=collection.name,
                        points_selector=models.Filter(must=[]),
                        wait=True,
                    )
                    print_status("OK", f"Cleared points in collection: {collection.name}", "green")
                except Exception as e:
                    print_status("WARN", f"Could not clear collection {collection.name}: {e}", "yellow")
                    raise
        
        print_status("OK", "Qdrant points cleared (collections preserved)", "green")
        return True
        
    except Exception as e:
        print_status("FAILED", f"Qdrant reset failed: {e}", "red")
        print(color_text("   Make sure Qdrant is running: docker-compose ps qdrant", "red"))
        return False

def main():
    parser = argparse.ArgumentParser(description="Reset system data ([WARNING] DESTRUCTIVE)")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--database-only", action="store_true", help="Reset only database")
    parser.add_argument("--redis-only", action="store_true", help="Reset only Redis")
    parser.add_argument("--qdrant-only", action="store_true", help="Reset only Qdrant")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(color_text("SYSTEM RESET", "blue"))
    print("=" * 60)
    print(color_text("[WARNING] WARNING: This will DELETE all system records!", "yellow"))
    print(color_text("   - Database table records (schema preserved)", "yellow"))
    print(color_text("   - Redis cache", "yellow"))
    print(color_text("   - Qdrant points (collections preserved)", "yellow"))
    print("="*60)
    
    if not args.force:
        confirm = input(color_text("\n[CONFIRM] Are you SURE? (type 'reset' to confirm): ", "yellow"))
        if confirm != "reset":
            print(color_text("Cancelled.", "yellow"))
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
        print_status("FAILED", "Some resets failed. Check errors above.", "red")
        sys.exit(1)

if __name__ == "__main__":
    main()
