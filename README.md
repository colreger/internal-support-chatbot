# Internal Support Chatbot

A Python and Streamlit assistant for internal support. It finds evidence in a fictional company library, filters documents by the signed-in user's permissions, and runs a validated tool call for travel reimbursements. An earlier document Q&A version was deployed to Azure Container Apps.

## Portfolio demo

The walkthrough uses the same claim lookup, policy index and validated calculator as the Streamlit application. It supplies a prepared tool call and runs without an API key.

From the repository root with Python 3.12 or 3.13:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements-api.txt
python demo_walkthrough.py
```

| Step | What to look for |
| --- | --- |
| Ask about RK-1042 | Gandalf sees the status and policy excerpt. Galadriel receives the same response as for an unknown claim. |
| Ask about the general rule | Galadriel can still retrieve the policy on private expenses. |
| Execute a tool call | Python validates the arguments and calculates EUR 275.40 in reimbursement from EUR 307.70 submitted. |

To try the same workflow in the interface, follow [Privacy pilot: run locally](#privacy-pilot-run-locally). The [LangChain and LangGraph examples](examples/langchain_recovery/README.md) show a separate recovery workflow that retries retrieval when evidence is insufficient.

## Travel claim status · fictional municipality

In Streamlit, sign in and open **Reisekostenstatus**. Look up `RK-1042` as Gandalf and then as Galadriel. The tab uses the same Python service as the FastAPI endpoint below.

The **Frage zu Reisekosten** form also accepts a free-text question such as `Wie ist der Stand meiner Abrechnung RK-1042?`. A LangGraph workflow with deterministic routing and LangChain tools uses a claim number when present, asks for one on status questions without an ID, and otherwise searches the permitted policy documents. A clarification is a prompt for a new question that includes the ID.

### API access

The local pilot combines an authenticated SQLite lookup with a source excerpt from the company library. The fixture contains one fictional record. The endpoint sends neither the claim nor the question to a model.

```bash
python -m pip install -r requirements-api.txt
python scripts/setup_demo.py  # once, if demo accounts have not been created
python -m uvicorn claims_api:app --host 127.0.0.1
```

Open Swagger at `http://127.0.0.1:8000/docs`. Use **Authorize** with Gandalf's generated credentials and request `GET /claims/RK-1042`. The response contains the status, deduction reason and relevant policy excerpt. Repeat with Galadriel. The same 404 is returned for a missing claim and a claim belonging to another account.

For the same free-text workflow, use `POST /ask` with a JSON body containing `question`. Streamlit and FastAPI invoke the same LangGraph workflow. The request identity is bound to the tools by the server and is absent from their argument schemas.

The account comes from the verified local login. The parameterized query filters by account and projects only the two fields needed for the answer. The response is marked `no-store`. The demo uses HTTP Basic on loopback and an in-memory fixture. Keep this endpoint local. Managed identity and persistent storage would be separate deployment work.

Run the API regression tests after installing the API dependencies:

```bash
python -m unittest discover -s api_tests -v
```

The tests use temporary demo accounts and verify owner access, a uniform response for foreign and missing claims, common policy access, clarification and input validation.

## Framework choices

- **LangGraph** routes each travel question to the claim tool, policy search or clarification. Each request ends after one branch.
- **LangChain** defines the claim and policy tools. The optional external answer path uses the ChatNVIDIA integration and retains the request preview and explicit send controls.
- **Python and SQLite** enforce account permissions, run parameterized queries and calculate reimbursements. The offline flow performs no external model calls.

See [support_workflow.py](support_workflow.py) for the graph and [claims.py](claims.py) for the account-scoped query.

## Overview

The RAG Knowledge Assistant lets users upload a PDF or text document and ask questions about its contents. Instead of relying solely on a language model's general knowledge, the application retrieves relevant document passages and provides them as context for answer generation.

**Tech stack:** Python · Streamlit · PDF/text processing · Sentence Transformers · Retrieval-Augmented Generation (RAG) · NVIDIA API · Docker · Azure Container Registry · Azure Container Apps

## How it works

1. **Upload:** The user uploads a PDF or TXT file in the Streamlit interface.
2. **Process:** The application extracts text and splits it into passages.
3. **Embed:** A sentence-transformer model represents text as numerical vectors.
4. **Retrieve:** Similarity-based retrieval selects relevant passages for the question.
5. **Generate:** A language model receives the question and retrieved context, then generates an answer.

```text
PDF / TXT upload
       |
       v
Text extraction and chunking
       |
       v
Embeddings and similarity search
       |
       v
Retrieved document context
       |
       v
NVIDIA-hosted LLM
       |
       v
Answer in Streamlit
```

## Language model

The local pilot optionally uses **NVIDIA Nemotron 3.5 Lightning 30B A3B** through NVIDIA's OpenAI-compatible API:

- Model ID: `nvidia/nemotron-3.5-lightning-30b-a3b`
- API base URL: `https://integrate.api.nvidia.com/v1`
- Secret environment variable: `NVIDIA_API_KEY`

Model availability may change. The model can be replaced in `answer_machine.py`.

## Privacy pilot: run locally

The app requires a local account. **Firmenwissen** searches a shared, preloaded fictional company library, with a restricted HR document visible only to Galadriel. Private uploads remain separate and use Chroma vector search. NVIDIA requests are **disabled by default**; the local views show original passages without an API key. See [the company library walkthrough](docs/firmenwissen.md).

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python scripts/setup_demo.py
streamlit run frontend.py --server.address 127.0.0.1
```

The setup script generates two local accounts, `gandalf` and `galadriel`. Their random passwords are in `.rag-demo-access.md`; only password hashes are stored in `.rag-users.json`. Both files are excluded from Git and Docker. The script refuses to overwrite existing accounts.

MiniLM weights must already exist locally. To download the public weights once, before using documents:

```bash
python -c 'from sentence_transformers import SentenceTransformer; SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")'
```

Normal application inference uses local model files only. In the UI, add a fictional document in the privacy-demo tab, search for training days, inspect the exact NVIDIA request preview, switch accounts and test deletion.

For an optional **explicitly enabled** external answer, provide `NVIDIA_API_KEY` in the environment or `.env`, and start with:

```bash
RAG_ALLOW_EXTERNAL=true streamlit run frontend.py --server.address 127.0.0.1
```

The document must also be approved for external use; the user then reviews and explicitly sends the displayed request. No API requests are made just by searching.

- [Privacy concept](docs/Datenschutzkonzept_Entwurf_2026-11-05.md) describes the design goals.
- [Privacy in practice](docs/datenschutz-praxis.md) maps those goals to implementation and tests.
- [DPIA example draft](docs/DSFA_Work_Assistent_Entwurf.md) records the assumptions and open questions for a fictional enterprise scenario.

## Tool Calling demo

Install the [optional LangChain dependencies](examples/langchain_recovery/requirements.txt) to run the LangChain examples:

```bash
python -m pip install -r examples/langchain_recovery/requirements.txt
```

The [LangChain experiments](examples/langchain_recovery/README.md) cover retrieval recovery, an optional review step and tool calling.

The **LangChain** tab offers three tools: search fictional company policies, calculate fictional travel reimbursement, and search the public web. For web search, configure `BRAVE_SEARCH_API_KEY` in the environment or local `.env`. NVIDIA proposes a query. **Suchbegriffe an Brave senden** sends the displayed query to Brave Search and shows up to three results. **Tool-Ergebnis an NVIDIA senden** sends the displayed results back to NVIDIA for an answer. [Brave Search API documentation](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)

For a local guest preview with the two demo tabs:

```bash
RAG_LOCAL_PREVIEW=true RAG_ALLOW_EXTERNAL=true venv/bin/streamlit run frontend.py --server.address 127.0.0.1 --server.port 8502
```

The guest preview requires a loopback address and uses the fictional company library for document searches. It does not open the account configuration or private document store.

In the **Tool Calling** tab, choose **Abrechnung prüfen** or **Richtlinie suchen**. Click **Offline-Beispiel ausführen** for a prepared tool call and actual local execution. The calculator applies a fictional cap of €120 per hotel night, includes the already approved taxi and excludes the private minibar expense. The example yields €275.40 out of €307.70, using integer cents throughout. The search example reuses the company library.

For a live run, start with `RAG_ALLOW_EXTERNAL=true` and configure `NVIDIA_API_KEY` as above. Turn on **Live-Modus mit NVIDIA** and review each request before sending. Both tool schemas are offered. The model proposes a tool and its arguments, Python executes at most one validated call, and the follow-up includes the result with its matching `tool_call_id`. The search is limited to externally approved employee demo documents.

The existing document Q&A retrieves passages before the model runs. Here the model can request either retrieval or a deterministic calculation. See [tool_calling.py](tool_calling.py) and the [LangChain version of the same calculator](examples/langchain_recovery/README.md#reisekosten-tool-mit-langchain).

## Tests

```bash
python -m unittest discover -s tests -v
```

The legacy root-level `test_chroma.py` / `test_llm.py` snippets belong to the previous unrestricted interface; use the scoped tests above and the UI for the new pilot.

## Docker

Build the image:

```bash
docker build --platform linux/amd64 -t rag-knowledge-assistant:local .
```

Run locally with a read-only account configuration and a persistent data mount (create the data directory first):

```bash
mkdir -p privacy_rag_db
docker run --rm -p 127.0.0.1:8501:8501 \
  -v "$PWD/.rag-users.json:/run/rag/users.json:ro" \
  -v "$PWD/privacy_rag_db:/app/privacy_rag_db" \
  -e RAG_USERS_FILE=/run/rag/users.json \
  rag-knowledge-assistant:local
```

The image build preloads public embedding weights; document inference does not download models. The new privacy image has not been built or deployed during this change. The local-account pilot is not approved for public deployment.

## Azure deployment

The previous application version was deployed using the following components. The new privacy pilot has not been deployed to Azure:

- **Azure Container Registry (ACR):** Stores the Docker image.
- **Azure Container Apps:** Runs the containerized Streamlit application.
- **Azure Container Apps Secrets:** Stores the NVIDIA API key outside the image.
- **Environment variables:** Exposes the secret to the application as `NVIDIA_API_KEY`.

The deployment image is built for `linux/amd64` to match the target runtime. Deployment access may be disabled outside of demonstrations to limit public exposure and API usage.

## Security and limitations

- Never commit `.env` files, API keys, or credentials to Git.
- Keep the NVIDIA API key in environment variables or a secret manager.
- Do not upload confidential documents to a publicly accessible demo.
- This is a portfolio/learning project, not a production-hardened document-processing service.
- Retrieval quality depends on text extraction, chunking, embeddings, and the document content.
- A language model can still produce incorrect answers; retrieved passages should be checked.

## What I learned

This project provided hands-on experience with building an end-to-end RAG pipeline, integrating an external LLM API, packaging a Python application in Docker, deploying to Azure, configuring secrets, and debugging container, authentication, and model-availability issues.

## Possible next steps

- Evaluate retrieval quality on a representative question set.
- Add automated tests and CI/CD.
- Improve access controls and monitoring for production use.
- Compare alternative retrieval and reranking strategies.

## License

See the repository's license file, if provided.
