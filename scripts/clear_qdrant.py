import asyncio
import logging
import argparse
import os
from dotenv import load_dotenv
from core.qdrant_mcp import get_qdrant_client
from models.config import QdrantConfig
from qdrant_client.http.models import Filter, FieldCondition, MatchValue, FilterSelector

# Load environment variables from .env
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def clear_points(user_id: str = None):
    # Extract config from environment variables
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY")
    
    cfg = QdrantConfig(
        url=url,
        api_key=api_key
    )
    
    collections = [cfg.collection_name, cfg.full_resume_collection]
    
    logger.info(f"Connecting to Qdrant at {cfg.url}...")
    
    async with get_qdrant_client(cfg) as client:
        for coll in collections:
            if not coll:
                continue
            
            try:
                exists = await client.collection_exists(collection_name=coll)
                if not exists:
                    logger.warning(f"Collection '{coll}' does not exist. Skipping.")
                    continue
                
                # Build filter: either all or specific user
                if user_id:
                    delete_filter = Filter(
                        must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
                    )
                    log_msg = f"Clearing points for user '{user_id}' in {coll}"
                else:
                    delete_filter = Filter() # Matches all
                    log_msg = f"Clearing ALL points from collection: {coll}"

                logger.info(log_msg)
                
                await client.delete(
                    collection_name=coll,
                    points_selector=FilterSelector(filter=delete_filter)
                )
                logger.info(f"✓ {coll} points cleared.")
            except Exception as e:
                logger.error(f"Failed to clear collection '{coll}': {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear points from Qdrant collections.")
    parser.add_argument("--user_id", help="Optional user_id to clear only their points.")
    args = parser.parse_args()
    
    asyncio.run(clear_points(user_id=args.user_id))
