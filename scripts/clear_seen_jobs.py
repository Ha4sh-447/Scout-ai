#!/usr/bin/env python3
import asyncio
import os
import sys
from redis.asyncio import Redis

async def clear_cache(user_id: str):
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    client = Redis.from_url(redis_url, decode_responses=True)
    
    # Clear seen jobs
    key = f"seen_jobs:{user_id}"
    count = await client.scard(key)
    if count > 0:
        print(f"Deleting {count} seen jobs for user {user_id}...")
        await client.delete(key)
    else:
        print(f"No seen jobs found for user {user_id}")
        
    # Clear LLM parsing cache
    keys = await client.keys("llm_cache:*")
    if keys:
        print(f"Deleting {len(keys)} old LLM cache entries...")
        await client.delete(*keys)
    else:
        print("No LLM cache entries to clear.")
        
    print("Cache cleared successfully.")
    await client.aclose()

if __name__ == "__main__":
    target_user = sys.argv[1] if len(sys.argv) > 1 else "49ebc0b5-5f3d-4ccc-8693-7c4db5b2dad6"
    asyncio.run(clear_cache(target_user))
