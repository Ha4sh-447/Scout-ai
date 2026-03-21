import os
from builtins import RuntimeError, isinstance
from contextlib import asynccontextmanager

from qdrant_client import AsyncQdrantClient
from qdrant_client.http.models import Distance, VectorParams
from qdrant_client.http.exceptions import UnexpectedResponse

from models.config import MistralConfig, QdrantConfig

@asynccontextmanager
async def get_qdrant_client(cfg: QdrantConfig):
    """
    Connect to Qdrant using the native python async client.
    """
    client_kwargs = {}
    if cfg.url:
        client_kwargs["url"] = cfg.url
    if cfg.api_key:
        client_kwargs["api_key"] = cfg.api_key
        
    client = AsyncQdrantClient(**client_kwargs)
    try:
        yield client
    finally:
        pass

async def ensure_collection_exists(client: AsyncQdrantClient, collection_name: str, dim: int = 1024):
    try:
        exists = await client.collection_exists(collection_name=collection_name)
        if not exists:
            await client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        
        # Always try to ensure indices for filtered fields
        from qdrant_client.http.models import PayloadSchemaType
        for field in ["user_id", "resume_id"]:
            try:
                await client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD
                )
            except Exception:
                # Index might already exist
                pass
                
    except Exception as e:
        raise RuntimeError(f"Failed to ensure collection '{collection_name}' exists: {e}")


import uuid
from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue

async def qdrant_store(client: AsyncQdrantClient, collection_name: str, embedding: list[float], metadata: dict, point_id: str | None = None) -> None:
    """
    Store metadata and vector directly to Qdrant.
    """
    await ensure_collection_exists(client, collection_name)
    final_id = point_id or str(uuid.uuid4())
    
    await client.upsert(
        collection_name=collection_name,
        points=[
            PointStruct(
                id=final_id,
                vector=embedding,
                payload=metadata
            )
        ]
    )


async def qdrant_delete_user_data(client: AsyncQdrantClient, collection_name: str, user_id: str, resume_id: str | None = None) -> None:
    """
    Delete points for a specific user (and optionally a specific resume) from a collection.
    """
    try:
        exists = await client.collection_exists(collection_name=collection_name)
        if not exists:
            return

        must_conditions = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
        if resume_id:
            must_conditions.append(FieldCondition(key="resume_id", match=MatchValue(value=resume_id)))

        await client.delete(
            collection_name=collection_name,
            points_selector=Filter(must=must_conditions),
        )
    except Exception as e:
        # Don't fail the whole pipeline if deletion fails (e.g. collection doesn't exist yet)
        import logging
        logging.getLogger(__name__).warning(f"Failed to delete user data for {user_id} (resume: {resume_id}) in {collection_name}: {e}")

async def qdrant_find(
    client: AsyncQdrantClient,
    collection_name: str,
    query_embedding: list[float],
    user_id: str,
    resume_id: str | None = None,
    top_k: int = 5
) -> list[dict]:
    """
    Find top k points similar to the query for a specific user.
    Optionally filters by resume_id.
    """
    await ensure_collection_exists(client, collection_name)
    must_conditions = [FieldCondition(key="user_id", match=MatchValue(value=user_id))]
    if resume_id:
        must_conditions.append(FieldCondition(key="resume_id", match=MatchValue(value=resume_id)))

    results = await client.query_points(
        collection_name=collection_name,
        query=query_embedding,
        query_filter=Filter(must=must_conditions),
        limit=top_k,
    )

    # Format output to match previous structure for seamless integration
    return [
        {
            "id": hit.id,
            "score": hit.score,
            "metadata": hit.payload,
            "information": hit.payload.get("information", ""),
            "text": hit.payload.get("text", "")
        }
        for hit in results.points
    ]
