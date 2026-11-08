"""Read-only search and calculation tools for the fictional travel demo."""
import json

from answer_machine import MODEL, SYSTEM_PROMPT
from company_library import CompanyLibrary

DEMO_QUESTION = "Wann wird ein Taxi zum Flughafen bei einer Dienstreise erstattet?"
CALC_QUESTION = (
    "Wie viel wird nach der Demo-Regel erstattet? Mein Testbeleg enthält "
    "2 Hotelnächte zu je 129,90 €, ein bereits genehmigtes Taxi für 35,40 € "
    "und eine private Minibar-Ausgabe von 12,50 €."
)
TOOL_NAME = "search_company_policies"
TOOL = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": "Sucht lokal nach passenden Richtlinien in einer fiktiven Firmenbibliothek.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Kurze Suchbegriffe auf Deutsch"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}

CALCULATOR_NAME = "calculate_travel_claim"
AMOUNT_LIMIT = 1_000_000
HOTEL_CAP_CENTS = 12_000
CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": CALCULATOR_NAME,
        "description": (
            "Berechnet die Erstattung für einen fiktiven Reisekostenbeleg. "
            "Demo-Regel: maximal 120 EUR pro Hotelnacht, genehmigtes Taxi voll, private Ausgabe ausgeschlossen."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "hotel_nights": {"type": "integer", "minimum": 0, "maximum": 30},
                "hotel_rate_cents": {"type": "integer", "minimum": 0, "maximum": AMOUNT_LIMIT,
                                     "description": "Preis pro Hotelnacht in Eurocent"},
                "approved_taxi_cents": {"type": "integer", "minimum": 0, "maximum": AMOUNT_LIMIT,
                                       "description": "Bereits genehmigtes Taxi in Eurocent"},
                "private_expense_cents": {"type": "integer", "minimum": 0, "maximum": AMOUNT_LIMIT,
                                          "description": "Private Ausgabe in Eurocent"},
            },
            "required": ["hotel_nights", "hotel_rate_cents", "approved_taxi_cents", "private_expense_cents"],
            "additionalProperties": False,
        },
    },
}
CALC_ARGUMENTS = {
    "hotel_nights": 2, "hotel_rate_cents": 12_990, "approved_taxi_cents": 3_540, "private_expense_cents": 1_250,
}
DEMO_CASES = {
    CALC_QUESTION: (CALCULATOR_NAME, CALC_ARGUMENTS),
    DEMO_QUESTION: (TOOL_NAME, {"query": "Taxi Flughafen"}),
}


def offline_message(question):
    name, arguments = DEMO_CASES[question]
    return {
        "role": "assistant",
        "tool_calls": [{
            "id": "offline-demo-1",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
        }],
    }


def build_tool_request(question):
    if question not in DEMO_CASES:
        raise ValueError("Wähle eine der fiktiven Demo-Fragen.")
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "Wähle für eine Richtlinienfrage das Suchtool und für eine Abrechnung das Rechentool. "
                "Rufe das passende Tool einmal auf. Übergib alle Geldbeträge in ganzen Eurocent. "
                "Bei einer Berechnung zitiere das Feld reimbursable_eur wörtlich und erkläre die Abzüge. "
                "Antworte auf Deutsch in höchstens drei Sätzen. "
                "Bei einer Richtlinienfrage gilt: " + SYSTEM_PROMPT
            )},
            {"role": "user", "content": question},
        ],
        "tools": [CALCULATOR_TOOL, TOOL],
        "tool_choice": "auto",
        "temperature": 0,
        "max_tokens": 2048,
    }


def calculate_travel_claim(hotel_nights, hotel_rate_cents, approved_taxi_cents, private_expense_cents):
    """Apply the fictional hotel cap and report the claim in exact euro cents."""
    amounts = (hotel_rate_cents, approved_taxi_cents, private_expense_cents)
    if type(hotel_nights) is not int or not 0 <= hotel_nights <= 30:
        raise ValueError("Die Zahl der Hotelnächte muss eine ganze Zahl von 0 bis 30 sein.")
    if any(type(amount) is not int or not 0 <= amount <= AMOUNT_LIMIT for amount in amounts):
        raise ValueError("Beträge müssen in ganzen Eurocent zwischen 0 und 1.000.000 vorliegen.")

    hotel_submitted = hotel_nights * hotel_rate_cents
    hotel_allowed = hotel_nights * min(hotel_rate_cents, HOTEL_CAP_CENTS)
    reimbursable = hotel_allowed + approved_taxi_cents
    submitted = hotel_submitted + approved_taxi_cents + private_expense_cents
    euros, cents = divmod(reimbursable, 100)
    return {
        "submitted_cents": submitted,
        "reimbursable_cents": reimbursable,
        "reimbursable_eur": f"{euros},{cents:02d} €",
        "excluded_cents": submitted - reimbursable,
        "hotel_cap_per_night_cents": HOTEL_CAP_CENTS,
        "hotel_above_cap_cents": hotel_submitted - hotel_allowed,
        "private_expense_excluded_cents": private_expense_cents,
    }


def build_tool_followup(request, message, library, owner):
    calls = message.get("tool_calls") or []
    if not calls:
        return None
    if len(calls) != 1:
        raise ValueError("Die Demo akzeptiert genau einen Tool-Aufruf.")

    call = calls[0]
    function = call.get("function") or {}
    name = function.get("name")
    if call.get("type") != "function" or name not in (TOOL_NAME, CALCULATOR_NAME) or not call.get("id"):
        raise ValueError("Dieser Tool-Aufruf ist nicht erlaubt.")
    try:
        arguments = json.loads(function.get("arguments", ""))
    except (ValueError, TypeError) as exc:
        raise ValueError("Die Tool-Argumente sind kein gültiges JSON.") from exc
    if name == CALCULATOR_NAME:
        required = CALCULATOR_TOOL["function"]["parameters"]["required"]
        if not isinstance(arguments, dict) or arguments.keys() != set(required):
            raise ValueError("Das Rechentool erwartet genau die vier Felder aus dem Schema.")
        result = json.dumps(calculate_travel_claim(**arguments), ensure_ascii=False)
    else:
        result = search_company_policies(arguments, library, owner)
    return {
        **request,
        "tool_choice": "none",
        "extra_body": {"chat_template_kwargs": {"enable_thinking": False}},
        "messages": [
            *request["messages"],
            {"role": "assistant", "tool_calls": [call]},
            {"role": "tool", "tool_call_id": call["id"], "content": result},
        ],
    }


def search_company_policies(arguments, library, owner):
    if (
        not isinstance(arguments, dict)
        or arguments.keys() != {"query"}
        or not isinstance(arguments["query"], str)
        or not 1 <= len(arguments["query"].strip()) <= 2000
    ):
        raise ValueError("Das Suchtool erwartet genau ein Textargument: query (1 bis 2.000 Zeichen).")

    # Filter before ranking. Account and corpus are selected by Python, outside model control.
    public_demo = CompanyLibrary(
        source for source in library.sources if source.external and source.role == "employee"
    )
    hits = public_demo.search(owner, arguments["query"])
    sources = "\n\n".join(f"[{i}] {hit.title}\n{hit.text}" for i, hit in enumerate(hits, 1))
    return sources or "Keine passenden Quellen."
