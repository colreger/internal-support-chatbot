# Implemented architecture: privacy pilot

Streamlit is the application and UI; there is no separate HTTP backend.

- `auth.py`: local password-hash verification and expiring server session.
- `document_processor.py`: bounded PDF/TXT extraction and 1,000-character chunks.
- `embeddings.py`: locally cached MiniLM model weights; no remote inference fallback.
- `vector_store.py`: persistent Chroma collection with mandatory account and document filters; scoped deletion and external-use approval.
- `rag_service.py`: retrieval, exact outgoing preview, and renewed authorization before sending.
- `answer_machine.py`: lazy NVIDIA client behind a default-off outbound switch.
- `frontend.py`: authenticated upload/edit/index flow, local source search, external preview/send flow and deletion.
- `tests/test_privacy.py`: privacy boundary tests and Streamlit flow verification.

See [the privacy implementation and walkthrough](datenschutz-praxis.md) for data flow, persistence, evidence and remaining production requirements. The prior shared Chroma collection is not read or migrated.
