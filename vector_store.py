"""Owner-scoped persistence. Legacy unowned collections are never queried."""
import os
import time
import uuid
from dataclasses import dataclass
from threading import RLock

import chromadb
from chromadb.config import Settings


@dataclass(frozen=True)
class Passage:
    chunk_id: str
    document_id: str
    source: str
    index: int
    text: str
    distance: float


class DocumentStore:
    def __init__(self, path=None):
        self.client = chromadb.PersistentClient(
            path=str(path or os.environ.get("RAG_DATA_DIR", "./privacy_rag_db")),
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name="private_document_chunks_v1",
            configuration={"hnsw": {"space": "cosine"}},
        )
        self.lock = RLock()

    @staticmethod
    def scope(owner, document_id=None):
        if not isinstance(owner, str) or not owner.strip():
            raise PermissionError("Anmeldung erforderlich.")
        if document_id is None:
            return {"owner": owner}
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("Dokument auswählen.")
        return {"$and": [{"owner": owner}, {"document_id": document_id}]}

    def add(self, owner, source, chunks, embeddings, *, external_approved=False):
        self.scope(owner)
        if not chunks or not all(isinstance(c, str) and c.strip() for c in chunks):
            raise ValueError("Keine lesbaren Textabschnitte vorhanden.")
        vectors = embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings
        if len(vectors) != len(chunks):
            raise ValueError("Für jeden Abschnitt wird ein Vektor benötigt.")
        source = source.strip()[:120]
        if not source:
            raise ValueError("Dokumenttitel fehlt.")
        document_id = uuid.uuid4().hex
        ids = [f"{document_id}:{index}" for index in range(len(chunks))]
        now = time.time()
        metadata = [{"owner": owner, "document_id": document_id, "source": source,
                     "index": i, "external_approved": bool(external_approved),
                     "created_at": now} for i in range(len(chunks))]
        with self.lock:
            self.collection.add(ids=ids, documents=chunks, embeddings=vectors, metadatas=metadata)
        return document_id

    def documents(self, owner):
        with self.lock:
            rows = self.collection.get(where=self.scope(owner), include=["metadatas"])
        docs = {}
        for meta in rows["metadatas"]:
            item = docs.setdefault(meta["document_id"], {
                "document_id": meta["document_id"], "source": meta["source"],
                "external_approved": meta["external_approved"], "chunks": 0,
                "created_at": meta["created_at"],
            })
            item["chunks"] += 1
        return sorted(docs.values(), key=lambda d: d["created_at"], reverse=True)

    def document(self, owner, document_id):
        self.scope(owner, document_id)
        return next((d for d in self.documents(owner) if d["document_id"] == document_id), None)

    def query(self, owner, document_id, query_embedding, n_results=3):
        with self.lock:
            doc = self.document(owner, document_id)
            if doc is None:
                return []
            vector = query_embedding.tolist() if hasattr(query_embedding, "tolist") else query_embedding
            rows = self.collection.query(
                query_embeddings=[vector], where=self.scope(owner, document_id),
                n_results=min(n_results, doc["chunks"]),
                include=["documents", "metadatas", "distances"],
            )
            return [Passage(chunk_id, meta["document_id"], meta["source"], meta["index"], text, distance)
                    for chunk_id, meta, text, distance in zip(
                        rows["ids"][0], rows["metadatas"][0], rows["documents"][0], rows["distances"][0])]

    def get_chunk(self, owner, document_id, chunk_id):
        with self.lock:
            rows = self.collection.get(ids=[chunk_id], where=self.scope(owner, document_id),
                                       include=["documents"])
        return rows["documents"][0] if rows["documents"] else None

    def approve_external(self, owner, document_id, approved):
        with self.lock:
            rows = self.collection.get(where=self.scope(owner, document_id), include=["metadatas"])
            if not rows["ids"]:
                raise PermissionError("Dokument nicht verfügbar.")
            metadata = [{**m, "external_approved": bool(approved)} for m in rows["metadatas"]]
            self.collection.update(ids=rows["ids"], metadatas=metadata)

    def delete(self, owner, document_id):
        with self.lock:
            rows = self.collection.get(where=self.scope(owner, document_id), include=[])
            if rows["ids"]:
                self.collection.delete(ids=rows["ids"], where=self.scope(owner, document_id))
            remaining = self.collection.get(where=self.scope(owner, document_id), include=[])
            if remaining["ids"]:
                raise RuntimeError("Löschung konnte nicht bestätigt werden.")
            return len(rows["ids"])
