import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from auth import authenticate, hash_password, valid_session
from answer_machine import send_request
from rag_service import Preview, RagService
from vector_store import DocumentStore


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = DocumentStore(self.temp.name)
        self.sent = []
        self.embedded = []

        def embed(question):
            self.embedded.append(question)
            return [1.0, 0.0]
        self.service = RagService(self.store, embed, sender=lambda request: self.sent.append(request) or "Antwort [1]")
        self.alice = self.store.add("alice", "Neutral", ["ALICE-SECRET: 17 Tage"], [[1.0, 0.0]])
        self.bob = self.store.add("bob", "Neutral", ["BOB-SECRET: 29 Tage"], [[1.0, 0.0]])
        self.env = patch.dict(os.environ, {"RAG_ALLOW_EXTERNAL": "true"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_other_owner_never_appears_even_with_identical_vectors(self):
        self.assertEqual(len(self.store.documents("alice")), 1)
        results = self.service.search("alice", self.alice, "Tage?")
        self.assertEqual([p.text for p in results], ["ALICE-SECRET: 17 Tage"])
        self.assertEqual(self.store.query("alice", self.bob, [1.0, 0.0]), [])
        self.assertIsNone(self.store.get_chunk("alice", self.bob, f"{self.bob}:0"))

    def test_foreign_id_is_rejected_before_embedding(self):
        with self.assertRaises(PermissionError):
            self.service.preview("alice", self.bob, "BOB-SECRET?")
        self.assertEqual(self.embedded, [])
        self.assertEqual(self.sent, [])

    def test_external_disabled_and_document_approval_each_block_send(self):
        preview = self.service.preview("alice", self.alice, "Tage?")
        self.assertEqual(self.sent, [])
        with self.assertRaises(PermissionError):
            self.service.send("alice", preview)
        self.store.approve_external("alice", self.alice, True)
        with patch.dict(os.environ, {"RAG_ALLOW_EXTERNAL": "false"}):
            with self.assertRaises(PermissionError):
                self.service.send("alice", preview)
        self.assertEqual(self.sent, [])

    def test_only_reviewed_owned_question_and_sources_are_sent(self):
        self.store.approve_external("alice", self.alice, True)
        preview = self.service.preview("alice", self.alice, "Wie viele Tage?")
        self.assertEqual(self.service.send("alice", preview), "Antwort [1]")
        self.assertEqual(len(self.sent), 1)
        serialized = json.dumps(self.sent[0])
        self.assertIn("ALICE-SECRET", serialized)
        self.assertIn("Wie viele Tage?", serialized)
        for excluded in ["BOB-SECRET", self.alice, self.bob, "Neutral", '"owner"']:
            self.assertNotIn(excluded, serialized)
        self.assertEqual(json.loads(preview.payload_json), self.sent[0])

    def test_foreign_or_modified_preview_cannot_be_sent(self):
        self.store.approve_external("alice", self.alice, True)
        preview = self.service.preview("alice", self.alice, "Tage?")
        with self.assertRaises(PermissionError):
            self.service.send("bob", preview)
        forged = Preview("alice", self.alice, preview.question, '{"messages": "forged"}')
        with self.assertRaises(PermissionError):
            self.service.send("alice", forged)
        self.assertEqual(self.sent, [])

    def test_revocation_blocks_already_created_preview(self):
        self.store.approve_external("alice", self.alice, True)
        preview = self.service.preview("alice", self.alice, "Tage?")
        self.store.approve_external("alice", self.alice, False)
        with self.assertRaises(PermissionError):
            self.service.send("alice", preview)
        self.assertEqual(self.sent, [])

    def test_deletion_removes_vectors_text_ids_and_blocks_pending_send(self):
        self.store.approve_external("alice", self.alice, True)
        preview = self.service.preview("alice", self.alice, "Tage?")
        self.assertEqual(self.store.delete("bob", self.alice), 0)
        self.assertEqual(self.store.delete("alice", self.alice), 1)
        self.assertEqual(self.store.delete("alice", self.alice), 0)
        self.assertEqual(self.store.documents("alice"), [])
        self.assertEqual(self.store.query("alice", self.alice, [1.0, 0.0]), [])
        self.assertIsNone(self.store.get_chunk("alice", self.alice, f"{self.alice}:0"))
        # The underlying active database record is gone, including its embedding.
        self.assertEqual(self.store.collection.get(ids=[f"{self.alice}:0"], include=["embeddings"])["ids"], [])
        with self.assertRaises(PermissionError):
            self.service.send("alice", preview)
        reopened = DocumentStore(self.temp.name)
        self.assertIsNone(reopened.document("alice", self.alice))
        self.assertIsNotNone(reopened.document("bob", self.bob))

    def test_same_filename_never_overwrites_another_document(self):
        second = self.store.add("alice", "Neutral", ["Neue Version"], [[0.0, 1.0]])
        self.assertNotEqual(self.alice, second)
        self.assertEqual(len(self.store.documents("alice")), 2)
        self.store.delete("alice", self.alice)
        self.assertEqual(self.store.get_chunk("alice", second, f"{second}:0"), "Neue Version")

    def test_empty_owner_fails_closed(self):
        with self.assertRaises(PermissionError):
            self.store.documents("")

    def test_gateway_sends_exact_payload_without_real_network(self):
        self.store.approve_external("alice", self.alice, True)
        preview = self.service.preview("alice", self.alice, "Tage?")
        payload = json.loads(preview.payload_json)
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "fake-test-key"}), patch("openai.OpenAI") as client:
            sdk = client.return_value.__enter__.return_value
            sdk.chat.completions.create.return_value.choices[0].message.content = "17 Tage [1]"
            self.assertEqual(send_request(payload), "17 Tage [1]")
            sdk.chat.completions.create.assert_called_once_with(**payload)
            self.assertEqual(client.call_args.kwargs["base_url"], "https://integrate.api.nvidia.com/v1")
            self.assertEqual(client.call_args.kwargs["max_retries"], 0)
        with patch.dict(os.environ, {"RAG_ALLOW_EXTERNAL": "false"}), patch("openai.OpenAI") as client:
            with self.assertRaises(PermissionError):
                send_request(payload)
            client.assert_not_called()

    def test_authentication_expiry_and_config_rotation(self):
        users = {"alice": hash_password("a sufficiently long test password")}
        self.assertTrue(authenticate("alice", "a sufficiently long test password", users))
        self.assertFalse(authenticate("alice", "wrong", users))
        self.assertFalse(authenticate("unknown", "wrong", users))
        session = {"owner": "alice", "issued_at": 100, "config_version": "v1"}
        self.assertTrue(valid_session(session, users, "v1", now=101))
        self.assertFalse(valid_session(session, users, "v1", now=1900))
        self.assertFalse(valid_session(session, users, "v2", now=101))
        self.assertFalse(valid_session(session, {}, "v1", now=101))


class StreamlitPrivacyTests(unittest.TestCase):
    def test_login_search_preview_revoke_delete_logout(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest
        import numpy as np
        st.cache_resource.clear()
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "users.json"
            config.write_text(json.dumps({"alice": hash_password("test-password"), "bob": hash_password("other-password")}))
            with patch.dict(os.environ, {"RAG_USERS_FILE": str(config), "RAG_DATA_DIR": str(Path(temp) / "db"),
                                         "RAG_ALLOW_EXTERNAL": "false"}), \
                    patch("embeddings.create_embeddings", side_effect=lambda texts: np.array([[1., 0.]] * len(texts))), \
                    patch("embeddings.create_query_embedding", return_value=np.array([1., 0.])):
                app = AppTest.from_file("frontend.py", default_timeout=30).run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.file_uploader) if hasattr(app, "file_uploader") else 0, 0)
                app.text_input[0].input("alice")
                app.text_input[1].input("test-password")
                next(b for b in app.button if b.label == "Anmelden").click().run()
                self.assertFalse(app.exception)
                # AppTest does not emulate file uploads; provide the empty browser state.
                for element in app.get("file_uploader"):
                    app.session_state[element.id] = None
                next(w for w in app.text_input if w.label == "Frage zum Firmenwissen").input("Taxi Flughafen")
                next(b for b in app.button if b.label == "Firmenwissen durchsuchen").click().run()
                self.assertFalse(app.exception)
                self.assertTrue(any("zumutbare Verbindung" in item.value for item in app.text))
                self.assertFalse(any("Gehaltsband" in item.value for item in app.text))
                next(b for b in app.button if b.label == "Fiktives Testdokument für mein Konto anlegen").click().run()
                self.assertFalse(app.exception)
                app.text_input(key="question_input").input("Wie viele Fortbildungstage?")
                next(b for b in app.button if b.label == "Lokal suchen und Anfragevorschau erstellen").click().run()
                self.assertFalse(app.exception)
                private_tab = next(tab for tab in app.tabs if tab.label == "Private Suche")
                private_previews = private_tab.get("json")
                self.assertEqual(len(private_previews), 1)
                self.assertIn("ALICE-KIESEL-731", private_previews[0].value)
                self.assertNotIn("BOB-LINDE-942", private_previews[0].value)
                send = next(b for b in app.button if b.label == "Geprüfte Anfrage jetzt an NVIDIA senden")
                self.assertTrue(send.disabled)
                next(b for b in app.button if b.label == "Externe Freigabe erteilen").click().run()
                self.assertFalse(app.exception)
                self.assertNotIn("preview", app.session_state)
                next(c for c in app.checkbox if c.label.startswith("Dieses Dokument mit allen Chunks")).check().run()
                next(b for b in app.button if b.label == "Dokument endgültig aus aktivem Suchbestand löschen").click().run()
                self.assertFalse(app.exception)
                self.assertNotIn("preview", app.session_state)
                self.assertFalse(app.selectbox)
                next(b for b in app.button if b.label == "Abmelden und Sitzung leeren").click().run()
                self.assertFalse(app.exception)
                self.assertNotIn("login", app.session_state)
        st.cache_resource.clear()


if __name__ == "__main__":
    unittest.main()
