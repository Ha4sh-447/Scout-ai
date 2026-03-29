#!/usr/bin/env python3
"""
Clear/Reset Qdrant vector database collections.
Works with Docker setup via http://qdrant:6333

Usage:
    python scripts/clear_qdrant.py              # Clear resume_chunks collection
    python scripts/clear_qdrant.py --all        # Delete ALL collections
    python scripts/clear_qdrant.py --collection resume_chunks  # Delete specific collection
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from qdrant_client import QdrantClient

# Load environment variables
load_dotenv()

def get_qdrant_client():
    """Get Qdrant client pointing to Docker service"""
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    
    try:
        client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        print(f"[OK] Connected to Qdrant at {qdrant_url}")
        return client
    except Exception as e:
        print(f"[FAILED] Failed to connect to Qdrant at {qdrant_url}")
        print(f"   Error: {e}")
        print(f"   Are Docker services running? Try: docker-compose ps")
        sys.exit(1)

def clear_collection(client: QdrantClient, collection_name: str):
    """Delete a specific collection"""
    try:
        client.delete_collection(collection_name)
        print(f"[OK] Deleted collection: {collection_name}")
        return True
    except Exception as e:
        print(f"[FAILED] Error deleting collection {collection_name}: {e}")
        return False

def clear_all_collections(client: QdrantClient):
    """List and delete all collections"""
    try:
        collections = client.get_collections().collections
        if not collections:
            print("[INFO] No collections to delete")
            return True
        
        print(f"Found {len(collections)} collections:")
        for collection in collections:
            print(f"  - {collection.name}")
        
        confirm = input("\n[WARNING] Delete ALL collections? (yes/no): ")
        if confirm.lower() != "yes":
            print("Cancelled.")
            return False
        
        deleted_count = 0
        for collection in collections:
            if clear_collection(client, collection.name):
                deleted_count += 1
        
        print(f"\n[OK] Deleted {deleted_count}/{len(collections)} collections")
        return True
    except Exception as e:
        print(f"[FAILED] Error listing collections: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Clear Qdrant collections")
    parser.add_argument("--all", action="store_true", help="Delete ALL collections (with confirmation)")
    parser.add_argument("--collection", type=str, default="resume_chunks", help="Collection name to delete (default: resume_chunks)")
    
    args = parser.parse_args()
    
    client = get_qdrant_client()
    
    if args.all:
        success = clear_all_collections(client)
    else:
        print(f"Clearing collection: {args.collection}")
        success = clear_collection(client, args.collection)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
