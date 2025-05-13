"""
worker/ingest.py
────────────────
Celery worker that

1. pulls the uploaded file bytes from Redis
2. extracts / chunks text
3. generates Gemini embeddings (vector length = 768)
4. upserts points into the `document` collection in Qdrant
"""
from __future__ import annotations

import os
from io import BytesIO
from uuid import UUID

import google.generativeai as genai
import magic
from celery import Celery
from celery.signals import worker_process_init
from redis import Redis
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant
from qdrant_client.http.exceptions import UnexpectedResponse
from unstructured.partition.auto import partition
from unstructured.partition.text import partition_text

from app.core.config import get_settings

# ──────────────────────────────────────────────────────────────────────────────
# ❶  Global configuration (only once per worker process)
# ──────────────────────────────────────────────────────────────────────────────
settings = get_settings()

# -- Redis --------------------------------------------------------------------
redis = Redis.from_url(settings.redis_url, decode_responses=False)  # RAW bytes!

# -- Google AI ----------------------------------------------------------------
genai.configure(api_key=settings.gemini_api_key or os.getenv("GOOGLE_API_KEY"))
EMBED_MODEL = "models/embedding-001"  # public model, vector size 768
VECTOR_DIM = 768

# -- Qdrant -------------------------------------------------------------------
qdrant_cli = QdrantClient(url=settings.qdrant_url)
COLLECTION = "document"


@worker_process_init.connect
def _ensure_qdrant_collection(**_):
    """
    Runs once per worker *process* before any task executes.
    Creates the collection if it isn't there – if another process beat us to it
    we silently swallow Qdrant's 409 Conflict.
    """
    try:
        if COLLECTION not in {c.name for c in qdrant_cli.get_collections().collections}:
            qdrant_cli.create_collection(
                collection_name=COLLECTION,
                vectors_config=qdrant.VectorParams(
                    size=VECTOR_DIM, distance=qdrant.Distance.COSINE
                ),
            )
    except UnexpectedResponse as exc:
        if "already exists" not in str(exc):
            raise


# -- Celery -------------------------------------------------------------------
celery_app = Celery(
    "worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    task_serializer="json",
    result_serializer="json",
)

# ──────────────────────────────────────────────────────────────────────────────
# ❷  Helper functions
# ──────────────────────────────────────────────────────────────────────────────
def gemini_embed(texts: list[str]) -> list[list[float]]:
    """Call Gemini embed endpoint; returns list[list[float]] (len == 768)."""
    vectors: list[list[float]] = []
    for txt in texts:
        res = genai.embed_content(
            model=EMBED_MODEL,
            content=txt,
            task_type="SEMANTIC_SIMILARITY",
        )
        vectors.append(res["embedding"])
    return vectors


def safe_payload(file_id: UUID | str, idx: int, chunk: str, filename: str) -> dict:
    """Return a pure-JSON payload – no UUID objects, no None, no bytes."""
    return {
        "file_id": str(file_id),
        "chunk_idx": idx,
        "text": chunk,
        "filename": filename,
    }


# ──────────────────────────────────────────────────────────────────────────────
# ❸  Celery task
# ──────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="ingest_document")
def ingest_document(file_id: str, filename: str) -> str:
    """
    • Pull file bytes from Redis
    • Partition → full_text
    • Chunk ~1200 chars   (≈ ~350 tokens)
    • Embed & upsert
    """
    # ---------------------------------------------------------------- fetch
    raw: bytes | None = redis.get(f"file:{file_id}")
    if raw is None:
        return "Redis key expired (upload again)."

    # ---------------------------------------------------------------- extract
    # Get first 2 KiB *directly from bytes* for libmagic
    header = raw[:2048]
    try:
        mime = magic.from_buffer(header, mime=True)  # needs libmagic1

        if mime == "text/plain" or filename.lower().endswith(".txt"):
            # Simple .txt → split into paragraphs
            elements = partition_text(text=raw.decode("utf-8", errors="ignore"))
        else:
            # PDF, DOCX, MD, PPTX, …
            buffer = BytesIO(raw)
            buffer.seek(0)  # make sure the stream is at the beginning
            elements = partition(file=buffer)
    except Exception as exc:
        return f"Partition-error: {exc}"

    full_text = "\n".join(str(el) for el in elements)
    if not full_text.strip():
        return "No textual content found."

    # ---------------------------------------------------------------- chunk
    CHUNK_SIZE = 1_200
    chunks = [
        full_text[i : i + CHUNK_SIZE] for i in range(0, len(full_text), CHUNK_SIZE)
    ]

    # ---------------------------------------------------------------- embed
    vectors = gemini_embed(chunks)
    if any(len(v) != VECTOR_DIM for v in vectors):
        raise ValueError("Vector dimension mismatch!")

    # ---------------------------------------------------------------- upsert
    points: list[qdrant.PointStruct] = []
    for idx, (vec, chunk) in enumerate(zip(vectors, chunks)):
        points.append(
            qdrant.PointStruct(
                id=f"{file_id}-{idx}",
                vector=vec,  # singular “vector”
                payload=safe_payload(file_id, idx, chunk, filename),
            )
        )

    qdrant_cli.upsert(collection_name=COLLECTION, points=points, wait=True)
    return f"Inserted {len(points)} chunks for file {filename}"
