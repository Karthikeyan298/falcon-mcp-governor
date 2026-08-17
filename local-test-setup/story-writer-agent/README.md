# Story Writer Agent

Angular UI → FastAPI backend → LangGraph agent that generates a story with a
local Llama model (via Ollama), saves it through a database MCP server, and
emails it through a separate email MCP server. Both MCP servers are HTTP
transport; the agent discovers their tools at runtime instead of hardcoding
tool names, so it adapts to whatever tools each server actually exposes.

## Architecture

```
Angular (title + recipient email)
        │  POST /api/stories
        ▼
FastAPI (backend/app/main.py)
        │
        ▼
LangGraph pipeline (backend/app/agent/graph.py)
  1. generate_story  → pluggable LLM provider (backend/app/llm), Ollama today
  2. store_story     → DB MCP server: list_tools() → pick best match → call_tool()
  3. send_email      → Email MCP server: list_tools() → pick best match → call_tool()
```

Tool discovery lives in `backend/app/mcp/resolver.py`: it scores each
advertised MCP tool's name/description against intent keywords ("save",
"store", "insert" for the DB; "send", "email", "notify" for email) and maps
our field names (title/content, to/subject/body) onto whatever argument names
the chosen tool's schema actually uses.

## Backend (FastAPI)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # edit MCP server URLs / LLM settings as needed
.venv/bin/uvicorn app.main:app --reload --port 9001
```

Config (`backend/.env`):

- `LLM_PROVIDER` / `LLM_MODEL` — currently only `ollama` is implemented; add
  new vendors in `app/llm/factory.py` + a new provider class in `app/llm/`.
- `OLLAMA_BASE_URL` — local Ollama server (default `http://localhost:11434`).
  Run `ollama pull llama3 && ollama serve` before generating stories.
- `DB_MCP_SERVER_URL` / `EMAIL_MCP_SERVER_URL` — your two HTTP MCP servers.
- `FRONTEND_ORIGIN` — CORS origin for the Angular dev server.

## Frontend (Angular)

```bash
cd frontend
npm install
npm start   # serves on http://localhost:4200
```

`src/environments/environment.ts` points the UI at
`http://localhost:9001/api` — update it if the backend runs elsewhere.

## Run end to end

1. Start Ollama, pull a model (`ollama pull llama3`).
2. Start your DB MCP server and email MCP server (HTTP transport).
3. Start the backend (port 9001) and frontend (port 4200).
4. Open http://localhost:4200, enter a title and a recipient email, submit.
