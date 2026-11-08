"""Only model weights are cached. Document text and query results are not cached."""
import os
from functools import lru_cache

# Inference must not send text or telemetry to the model hub.
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)


def create_embeddings(chunks):
    return get_model().encode(chunks, normalize_embeddings=True)


def create_query_embedding(query):
    return get_model().encode(query, normalize_embeddings=True)
