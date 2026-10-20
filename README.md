# PDF RAG — LangChain + Databricks

A minimal document-question-answering app: upload PDFs, index page-aware chunks in Databricks Vector Search, then ask questions and receive answers grounded in retrieved passages with PDF/page citations. FastAPI stores chat sessions and messages in PostgreSQL; the Next.js UI talks to the API.

## Architecture and flow

1. `POST /ingest` extracts each PDF page with `pypdf`, splits text into 1,000-character chunks with 150-character overlap, and retains filename, 1-based page, and stable chunk ID metadata.
2. LangChain Databricks embeddings and `DatabricksVectorSearch` write chunks to a configured **Direct Vector Access** index.
3. `POST /chat` retrieves the top four chunks, passes only those excerpts as answer context to the configured Databricks chat endpoint, and asks it to cite sources as `[filename, p. N]`.
4. The API returns the answer and distinct page citations and persists user/assistant messages against a PostgreSQL session UUID. The browser retains the UUID for follow-up questions.

## Stack and repository

- Backend: Python, FastAPI, LangChain, `databricks-langchain`, `pypdf`, psycopg 3.
- Frontend: Next.js App Router, React, TypeScript.
- Services: Databricks Model Serving, Databricks Vector Search, PostgreSQL.

```text
backend/app/       API, PDF ingestion, RAG, PostgreSQL
backend/            Python requirements and environment example
frontend/app/       Next.js chat UI
frontend/           npm manifest and environment example
```

## Prerequisites

- Python 3.10+ and Node.js 20+ with npm.
- PostgreSQL 12+ database and network access from the backend.
- Databricks workspace, credentials authorized for the configured endpoints, a chat-serving endpoint, an OpenAI-compatible embedding-serving endpoint, and a Vector Search endpoint/index.

### Databricks index setup

Create a **Direct Vector Access** index in Unity Catalog and a Vector Search endpoint. The index's primary key must be a string `id`, and its columns must include `text` (string), `text_vector` (array of floats, dimension matching the embedding endpoint), `source` (string), `page` (integer), and `chunk_id` (string). Configure the index embedding vector column as `text_vector`; the application supplies embeddings using the configured model endpoint. Make sure the index and Vector Search endpoint are ready before ingestion. The index must support direct upserts; a Delta Sync index is not suitable for this upload flow.

Choose an embedding model with a compatible dimension and set that dimension when creating the index. The SDK/API for creating indexes is evolving; create the endpoint/index with the Databricks UI or your workspace's supported Vector Search API. This application does not create Databricks resources.

The LangChain Databricks integration uses Databricks SDK authentication via `DATABRICKS_HOST` and `DATABRICKS_TOKEN` for local development. Use a least-privilege service principal/OAuth configuration for production rather than a personal token when available. The chat endpoint must accept LangChain `ChatDatabricks` chat requests; the embedding endpoint must accept `DatabricksEmbeddings` requests.

## Configure and run

Copy the example environment files and replace placeholders in local `.env` files. Never commit those files.

```sh
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Set every `DATABRICKS_*` endpoint/credential value in `backend/.env`; configure `DATABASE_URL` as a PostgreSQL connection URL. `FRONTEND_ORIGIN` defaults to `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` if the backend is not at `http://localhost:8000`.

Create a PostgreSQL database and user, then grant the user permission to create tables in that database/schema. On the first chat request, the API creates `sessions` and `messages` tables and an index automatically. Chat history is stored for the configured PostgreSQL database; PDFs and their text are stored in the configured Databricks index.

Start the API from the repository root:

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal, start the web app:

```sh
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. Upload a PDF using **Choose a PDF** and **Index PDF**, then ask a question. The health endpoint is <http://localhost:8000/health>. PDF upload is limited by available memory and the API server's request-size limits; this MVP does not provide authentication or per-user document isolation.

## API

- `GET /health` reports PostgreSQL availability and whether required Databricks configuration values are present. It does not probe Databricks endpoints.
- `POST /ingest` accepts `multipart/form-data` with a `file` field containing a PDF.

Example upload:

```sh
curl -F 'file=@report.pdf' http://localhost:8000/ingest
```

Response:

```json
{"filename":"report.pdf","chunks_indexed":18}
```

- `POST /chat` accepts a question and an optional session UUID.

```sh
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"What are the main findings?"}'
```

Response:

```json
{
  "session_id":"00000000-0000-0000-0000-000000000000",
  "answer":"The report identifies ... [report.pdf, p. 3]",
  "citations":[{"filename":"report.pdf","page":3}]
}
```

Reuse the returned `session_id` for follow-up questions. Citations are one-based PDF page numbers; the answer includes inline `[filename, p. N]` references, and `citations` returns unique source pages as structured values.

## Troubleshooting and limitations

- `/health` reports `degraded` until PostgreSQL is reachable and all Databricks environment values are set.
- Missing Databricks values, unavailable services, invalid/non-text PDFs, and indexing failures return clear HTTP errors. Check credentials, endpoint permissions, index schema/embedding dimension, and that the configured index is Direct Vector Access.
- Scanned/image-only PDFs have no extractable text; OCR is not implemented. Password-protected PDFs and oversized uploads may fail.
- Databricks and PostgreSQL resources/credentials were not available in this repository environment; external integrations have not been exercised here.
- This MVP has no user authentication, streaming responses, document deletion, or data isolation between users. It is intended as a minimal starting point, not a production deployment.
