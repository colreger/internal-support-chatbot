import os
import unittest
from unittest.mock import Mock, patch

from company_library import CompanyLibrary


class CompanyLibraryTests(unittest.TestCase):
    def setUp(self):
        self.library = CompanyLibrary.load_demo()

    def test_both_accounts_find_same_shared_policy(self):
        question = "Darf ich bei einer Dienstreise ein Taxi zum Flughafen nehmen?"
        alice = self.library.search("alice", question)
        self.assertEqual(alice, self.library.search("bob", question))
        self.assertEqual(alice[0].title, "Reisekostenrichtlinie")

    def test_hr_text_and_metadata_are_filtered_before_ranking(self):
        self.assertFalse(self.library.search("alice", "Nordstern 482"))
        self.assertNotIn("HR: interne Gehaltsband-Prüfung", self.library.titles("alice"))
        self.assertIn("HR-NORDSTERN-482", self.library.search("bob", "Nordstern 482")[0].text)
        self.assertEqual(self.library.search("unknown", "Taxi Flughafen"), [])

    def test_preview_and_sender_never_include_restricted_source(self):
        sender = Mock(return_value="Antwort")
        with patch.dict(os.environ, {"RAG_ALLOW_EXTERNAL": "true"}):
            self.assertIsNone(self.library.preview("bob", "Nordstern 482"))
            with self.assertRaises(PermissionError):
                self.library.send("bob", "Nordstern 482", {"forged": True}, sender=sender)
            question = "Taxi Flughafen"
            payload = self.library.preview("alice", question)
            self.assertNotIn("HR-NORDSTERN", str(payload))
            with self.assertRaises(PermissionError):
                self.library.send("alice", question, {"forged": True}, sender=sender)
            sender.assert_not_called()
            self.assertEqual(self.library.send("alice", question, payload, sender=sender), "Antwort")
            sender.assert_called_once_with(payload)

    def test_no_matching_terms_do_not_produce_a_hit(self):
        self.assertEqual(self.library.search("alice", "Quantencomputer"), [])
