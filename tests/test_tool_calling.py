import json
import unittest
from unittest.mock import Mock

from company_library import CompanyLibrary, Source
from tool_calling import (CALC_ARGUMENTS, CALC_QUESTION, DEMO_QUESTION, build_tool_followup,
                          build_tool_request, calculate_travel_claim, offline_message)


class ToolCallingTests(unittest.TestCase):
    def setUp(self):
        self.request = build_tool_request(DEMO_QUESTION)
        self.message = offline_message(DEMO_QUESTION)
        self.call = self.message["tool_calls"][0]

    def test_followup_contains_grounding_and_matches_call_id(self):
        library = CompanyLibrary.load_demo()
        followup = build_tool_followup(self.request, self.message, library, "alice")
        assistant, tool = followup["messages"][-2:]
        self.assertEqual(self.request["tool_choice"], "auto")
        self.assertEqual(followup["tool_choice"], "none")
        self.assertEqual(assistant["tool_calls"], [self.call])
        self.assertEqual(tool["role"], "tool")
        self.assertEqual(tool["tool_call_id"], self.call["id"])
        self.assertIn("[1] Reisekostenrichtlinie", tool["content"])
        self.assertIn("keine zumutbare Verbindung", tool["content"])

    def test_only_externally_approved_employee_sources_are_searchable(self):
        library = CompanyLibrary([
            Source("Demo", "Taxi Flughafen öffentlich", "employee", True),
            Source("Intern", "Taxi Flughafen gesperrt", "employee", False),
            Source("Personal", "Taxi Flughafen vertraulich", "hr", True),
        ])
        followup = build_tool_followup(self.request, self.message, library, "bob")
        self.assertEqual(followup["messages"][-1]["content"], "[1] Demo\nTaxi Flughafen öffentlich")
        followup = build_tool_followup(self.request, self.message, library, "unknown")
        self.assertEqual(followup["messages"][-1]["content"], "Keine passenden Quellen.")

    def test_rejects_invalid_arguments_before_searching(self):
        library = Mock()
        for arguments in ("{", '["Taxi"]', '{"query":3}', '{"query":" "}', '{"query":"Taxi","owner":"bob"}'):
            with self.subTest(arguments=arguments):
                self.call["function"]["arguments"] = arguments
                with self.assertRaises(ValueError):
                    build_tool_followup(self.request, self.message, library, "alice")
        self.assertEqual(library.mock_calls, [])

    def test_rejects_unknown_tool_and_multiple_calls(self):
        library = Mock()
        self.call["function"]["name"] = "delete_document"
        with self.assertRaises(ValueError):
            build_tool_followup(self.request, self.message, library, "alice")
        with self.assertRaises(ValueError):
            build_tool_followup(self.request, {"tool_calls": [self.call] * 2}, library, "alice")
        self.assertEqual(library.mock_calls, [])

    def test_no_call_has_no_followup(self):
        self.assertIsNone(build_tool_followup(self.request, {}, Mock(), "alice"))

    def test_calculator_returns_exact_cents_without_searching(self):
        library = Mock()
        followup = build_tool_followup(
            build_tool_request(CALC_QUESTION), offline_message(CALC_QUESTION), library, "alice"
        )
        result = json.loads(followup["messages"][-1]["content"])
        self.assertEqual(result["submitted_cents"], 30770)
        self.assertEqual(result["reimbursable_cents"], 27540)
        self.assertEqual(result["reimbursable_eur"], "275,40 €")
        self.assertEqual(result["hotel_above_cap_cents"], 1980)
        self.assertEqual(result["private_expense_excluded_cents"], 1250)
        self.assertEqual(result["excluded_cents"], 3230)
        self.assertEqual(library.mock_calls, [])

    def test_calculator_rejects_wrong_units_and_preserves_prices_below_cap(self):
        for amount in (-1, True, "12990", 129.90):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                calculate_travel_claim(**{**CALC_ARGUMENTS, "hotel_rate_cents": amount})
        result = calculate_travel_claim(**{**CALC_ARGUMENTS, "hotel_rate_cents": 10000})
        self.assertEqual(result["hotel_above_cap_cents"], 0)
        self.assertEqual(result["reimbursable_cents"], 23540)
