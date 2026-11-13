"""Local FastAPI demo for checking a fictional travel claim."""

from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, StringConstraints

from auth import authenticate, load_users
from claims import CLAIM_ID_PATTERN, claim_with_policy
from support_workflow import answer_travel_question
from company_library import CompanyLibrary

app = FastAPI(title="Internal Support Chatbot · Local Pilot")
security = HTTPBasic()
library = CompanyLibrary.load_demo()


class ClaimStatus(BaseModel):
    status: str
    deduction_reason: str
    policy_title: str
    policy_excerpt: str


def authenticated_account(credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> str:
    users, _ = load_users()
    if not authenticate(credentials.username, credentials.password, users):
        raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Basic"})
    return credentials.username


@app.get("/claims/{claim_id}", response_model=ClaimStatus)
def claim_status(
    claim_id: Annotated[str, StringConstraints(pattern=CLAIM_ID_PATTERN)],
    owner: Annotated[str, Depends(authenticated_account)],
    response: Response,
) -> ClaimStatus:
    headers = {"Cache-Control": "no-store"}
    try:
        result = claim_with_policy(library, owner, claim_id)
    except ValueError as exc:
        raise HTTPException(422, str(exc), headers=headers) from exc
    except LookupError as exc:
        raise HTTPException(503, "Policy unavailable", headers=headers) from exc
    if result is None:
        raise HTTPException(404, "No visible claim", headers=headers)

    response.headers.update(headers)
    return ClaimStatus(**result)


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class Evidence(BaseModel):
    title: str
    excerpt: str


class AskResponse(BaseModel):
    status: Literal["answered", "clarify", "not_found"]
    answer: str
    sources: list[Evidence]


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, owner: Annotated[str, Depends(authenticated_account)], response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        return answer_travel_question(library, owner, request.question)
    except LookupError as exc:
        raise HTTPException(503, "Policy unavailable", headers={"Cache-Control": "no-store"}) from exc
