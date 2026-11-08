"""Authorization is enforced before retrieval and again immediately before egress."""
import json
from dataclasses import dataclass
from answer_machine import build_request, external_enabled, send_request


@dataclass(frozen=True)
class Preview:
    owner: str
    document_id: str
    question: str
    payload_json: str


class RagService:
    def __init__(self, store, embed_query, sender=send_request):
        self.store = store
        self.embed_query = embed_query
        self.sender = sender

    def search(self, owner, document_id, question):
        if not question.strip() or len(question) > 2000:
            raise ValueError("Bitte eine Frage mit 1 bis 2.000 Zeichen eingeben.")
        # Check ownership before embedding or any external activity.
        if self.store.document(owner, document_id) is None:
            raise PermissionError("Dokument nicht verfügbar.")
        return self.store.query(owner, document_id, self.embed_query(question))

    def preview(self, owner, document_id, question):
        preview, _ = self.preview_with_passages(owner, document_id, question)
        return preview

    def preview_with_passages(self, owner, document_id, question):
        passages = self.search(owner, document_id, question)
        if not passages:
            raise ValueError("Keine Quellen vorhanden.")
        payload = json.dumps(build_request(question, passages), ensure_ascii=False, sort_keys=True)
        return Preview(owner, document_id, question, payload), passages

    def send(self, owner, preview):
        if not external_enabled():
            raise PermissionError("Externe KI ist serverseitig deaktiviert.")
        if owner != preview.owner:
            raise PermissionError("Vorschau gehört zu einem anderen Konto.")
        # Serialize delete/revoke/send within this single-process pilot.
        with self.store.lock:
            doc = self.store.document(owner, preview.document_id)
            if doc is None or not doc["external_approved"]:
                raise PermissionError("Dokument fehlt oder ist nicht für externe KI freigegeben.")
            current = self.preview(owner, preview.document_id, preview.question)
            if current.payload_json != preview.payload_json:
                raise PermissionError("Quellen geändert. Bitte eine neue Vorschau erstellen.")
            return self.sender(json.loads(current.payload_json))
