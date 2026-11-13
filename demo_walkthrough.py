"""Show the company search, access boundary and tool execution in one offline run."""

import json

from support_workflow import answer_travel_question
from company_library import CompanyLibrary
from tool_calling import CALC_QUESTION, build_tool_followup, build_tool_request, offline_message


def main():
    library = CompanyLibrary.load_demo()

    question = "Wie ist der Stand meiner Abrechnung RK-1042?"
    print("1. Ask the same question with two demo accounts")
    print(question)
    for owner in ("gandalf", "galadriel"):
        result = answer_travel_question(library, owner, question)
        print(f"{owner}: {result['answer']}")
        for source in result["sources"]:
            print(f"  {source['title']}: {source['excerpt']}")

    print("\n2. Ask for the common policy as Galadriel")
    result = answer_travel_question(library, "galadriel", "Wird die Minibar erstattet?")
    print(result["answer"])

    print("\n3. Validate and execute a prepared travel reimbursement tool call")
    proposal = offline_message(CALC_QUESTION)
    function = proposal["tool_calls"][0]["function"]
    print(f"Tool: {function['name']}")
    print(f"Arguments (amounts in cents): {function['arguments']}")
    followup = build_tool_followup(build_tool_request(CALC_QUESTION), proposal, library, "gandalf")
    result = json.loads(followup["messages"][-1]["content"])
    print(f"Submitted: {result['submitted_cents'] / 100:.2f} EUR")
    print(f"Reimbursable: {result['reimbursable_cents'] / 100:.2f} EUR")


if __name__ == "__main__":
    main()
