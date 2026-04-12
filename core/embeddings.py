import asyncio
import os

from mistralai.client import Mistral

_api_key = os.getenv("MISTRAL_API_KEY")

def get_mistral_client():
    if not _api_key:
        raise RuntimeError("MISTRAL_API_KEY is not set in environment variables.")
    return Mistral(api_key=_api_key)

_client = None

EMBED_MODEL = "mistral-embed"


async def embed_text(text: str) -> list[float]:
    text = text.strip()
    if not text:
        raise ValueError("Cannot embed empty string")

    client = get_mistral_client()
    response = await client.embeddings.create_async(
        model=EMBED_MODEL,
        inputs=[text],
    )
    return response.data[0].embedding


async def embed_texts(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    if not texts:
        return []

    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = [t.strip() for t in texts[i : i + batch_size] if t.strip()]
        if not batch:
            continue

        client = get_mistral_client()
        response = await client.embeddings.create_async(
            model=EMBED_MODEL,
            inputs=batch,
        )
        all_embeddings.extend(item.embedding for item in response.data)

        if i + batch_size < len(texts):
            await asyncio.sleep(0.2)

    return all_embeddings
