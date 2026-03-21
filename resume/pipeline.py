import logging
import uuid
from pathlib import Path
 
from core.embeddings import embed_text, embed_texts
from core.qdrant_mcp import (
    get_qdrant_client,
    qdrant_store,
    qdrant_delete_user_data,
)
from models.config import QdrantConfig, ResumeMatchingConfig
from resume.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)

async def process_resume_upload(
        pdf_path: str | Path,
        user_id: str,
        resume_id: str = "default",
        summary: str | None = None,
        qdrant_cfg: QdrantConfig | None = None,
        matching_cfg: ResumeMatchingConfig | None = None
        ) -> dict:

    qdrant_cfg = qdrant_cfg or QdrantConfig()
    matching_cfg = matching_cfg or ResumeMatchingConfig()

    # Parse pdf
    logger.info(f"[resume_pipeline] Parsing pdf for user {user_id} (resume: {resume_id}): {pdf_path}")
    resume = parse_pdf(pdf_path, user_id, matching_cfg)
    resume.resume_id = resume_id

    if not resume:
        raise ValueError("No chunks could be produced")

    # Embed chunks
    chunk_text = [ chunk.text for chunk in resume.chunks]
    logger.info(f"[resume_pipeline] Embedding {len(chunk_text)} chunks")
    chunk_embeddings = await embed_texts(chunk_text)

    if len(chunk_embeddings) != len(resume.chunks):
        raise RuntimeError("Embedding count mistmatch")

    for chunk, emb in zip(resume.chunks, chunk_embeddings):
        chunk.embeddings = emb

    # Embed full resume text
    full_text = resume.raw_text[:8000]
    logger.info("[resume_pipeline] Embedding full resume text")
    full_embedding = await embed_text(full_text)

    # ── Step 3: Store vectors via Native Qdrant Client ───────────────────────
    logger.info(f"[resume_pipeline] Storing {len(resume.chunks)} chunks & full vector")
    async with get_qdrant_client(qdrant_cfg) as client:
        # 3a. Clear existing data for this specific user+resume combination
        logger.info(f"[resume_pipeline] Clearing existing data for user {user_id}, resume {resume_id}")
        await qdrant_delete_user_data(client, qdrant_cfg.collection_name, user_id, resume_id=resume_id)
        await qdrant_delete_user_data(client, qdrant_cfg.full_resume_collection, user_id, resume_id=resume_id)

        # 3b. Store Chunks
        # We use a constant namespace for deterministic UUIDs
        NAMESPACE_UUID = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8') # DNS namespace

        for chunk in resume.chunks:
            # Create a deterministic UUID for this chunk (includes resume_id to avoid collisions)
            deterministic_id = str(uuid.uuid5(NAMESPACE_UUID, f"{user_id}_{resume_id}_{chunk.chunk_index}"))
            
            await qdrant_store(
                client=client,
                collection_name=qdrant_cfg.collection_name,
                embedding=chunk.embeddings,
                metadata={
                    "chunk_id":    chunk.chunk_id,
                    "user_id":     chunk.user_id,
                    "resume_id":   resume_id,
                    "section":     chunk.section,
                    "chunk_index": chunk.chunk_index,
                    "information": chunk.text,
                    "text": chunk.text,
                },
                point_id=deterministic_id,
            )
        logger.info(f"[resume_pipeline] Stored {len(resume.chunks)} chunks")

        # 3c. Store Full Resume
        full_deterministic_id = str(uuid.uuid5(NAMESPACE_UUID, f"{user_id}_{resume_id}_full"))
        
        await qdrant_store(
            client=client,
            collection_name=qdrant_cfg.full_resume_collection,
            embedding=full_embedding,
            metadata={
                "user_id":    user_id,
                "resume_id":  resume_id,
                "entry_type": "full_resume",
                "information": summary or full_text,
                "text": full_text,
                "summary": summary
            },
            point_id=full_deterministic_id,
        )
        logger.info(f"[resume_pipeline] Stored full resume vector (resume_id: {resume_id})")
 
    return {
        "chunks_stored":      len(resume.chunks),
        "resume_id":          resume_id,
        "full_resume_stored": True,
    }

