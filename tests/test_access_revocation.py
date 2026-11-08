import unittest

from company_library import CompanyLibrary
from scripts.check_sharepoint_access import check


class AccessRevocationTests(unittest.TestCase):
    def test_same_query_and_index_after_revocation(self):
        library = CompanyLibrary.load_demo()
        self.assertTrue(library.search("bob", "Nordstern 482"))
        self.assertEqual(library.search("bob", "Nordstern 482", hr_revoked=True), [])
        self.assertIsNone(library.preview("bob", "Nordstern 482", hr_revoked=True))
        self.assertTrue(library.search("bob", "Taxi Flughafen", hr_revoked=True))
        self.assertTrue(library.search("bob", "Nordstern 482"))

    def test_stale_graph_hit_does_not_override_current_access(self):
        def read(path, *, denied_ok=False):
            if path.startswith("/me?"):
                return {"id": "demo-user"}
            if "/root/search(" in path:
                return {"value": [{"id": "target"}]}
            if "/items/control?" in path:
                return {"id": "control"}
            self.assertTrue(denied_ok)
            return None

        self.assertEqual(check(read, "drive", "control", "target", "Nordstern", "hidden"),
                         (True, True, False))
        self.assertEqual(check(read, "drive", "control", "target", "Nordstern", "visible"),
                         (False, True, False))

    def test_missing_control_is_inconclusive(self):
        def read(path, *, denied_ok=False):
            return {"id": "demo-user"} if path.startswith("/me?") else None

        with self.assertRaises(RuntimeError):
            check(read, "drive", "control", "target", "Nordstern", "hidden")
