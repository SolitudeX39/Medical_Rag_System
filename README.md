# Medical RAG AI

A simple web app that lets you upload medical PDFs or CSVs, stores their text in a vector database, builds a knowledge graph in Neo4j, and answers questions through a chat interface.

---

## Quick start
1. **Clone the repo** and open the project root.
2. **Create environment variables**
   ```bash
   cp .env.example .env
   ```
   Fill in your API keys (Google Gemini, OpenAI, OpenRouter) and Neo4j credentials.
3. **Start the services**
   ```bash
   docker compose up -d   # runs Postgres+pgvector and Neo4j
   ```
4. **Run the backend**
   ```bash
   python -m venv .venv
   ./.venv/Scripts/Activate.ps1   # PowerShell
   pip install -r requirements.txt
   uvicorn backend.main:app --reload --port 8000
   ```
5. **Run the frontend**
   ```bash
   cd frontend
   npm install
   npm run dev   # http://localhost:3000
   ```

---

## How it works
### 1. Upload
* The user selects a **PDF** or **CSV** on the Upload page.
* The file is sent to `POST /upload`.
* For CSVs with columns `disease`, `common_symptom` and `treatment` the server runs a **NER + RDF pipeline** (`process_csv_to_rdf`).
* The NER step uses **scispaCy** models (`en_core_sci_sm` for symptoms and `en_ner_bc5cdr_md` for chemicals/treatments) with the **UMLS entity linker** to map extracted terms to CUI identifiers.
* The pipeline creates a Turtle (`.ttl`) file and streams it into Neo4j using the `n10s` plugin.
* The response includes:
  * `ner_summary` – a short message that the RDF conversion succeeded.
  * `graph` – a brief overview (node counts) of what was added to Neo4j.

### 2. Chat
* A new chat session can be started at any time.
* When the user sends a message, the backend calls `related_terms(message)` which queries Neo4j for nodes whose label contains the query text.
* Those nodes are added to the prompt sent to the language model (OpenAI / Gemini / OpenRouter).
* The answer is returned together with a **sub‑graph** containing only the relevant nodes and edges.
* The frontend displays the answer and renders the sub‑graph with `GraphView`.

---

## Workflow diagram
```mermaid
flowchart LR
    U[User] -->|Upload CSV| FE[Frontend Upload page]
    FE -->|POST /upload| API[FastAPI backend]
    API -->|Run NER + RDF| PIPE[process_csv_to_rdf]
    PIPE -->|Generate TTL| TTL[TTL file]
    TTL -->|Upload to Neo4j| NEO[Neo4j graph]
    API -->|Return status, ner_summary, graph overview| FE
    U -->|Start chat| ChatUI[Chat page]
    ChatUI -->|POST /chat| API
    API -->|Query Neo4j (related_terms)| NEO
    NEO -->|Relevant nodes/edges| API
    API -->|Compose prompt with graph data| LLM[LLM]
    LLM -->|Answer + graph dict| ChatUI
    ChatUI -->|Render GraphView| GraphView[Graph visualisation]
```

---

## Tech stack
| Layer | Technology |
|-------|------------|
| Frontend | Next.js 16, React 19, TypeScript 5, Tailwind CSS 4 |
| Backend | FastAPI, Uvicorn, Pydantic |
| Embedding | Google Gemini (`gemini-embedding-2`) |
| Chat model | OpenAI (`gpt-4o-mini`) – fall back to Gemini or OpenRouter |
| Rerank | OpenRouter LLM reranker |
| Vector store | PostgreSQL 16 + pgvector |
| Graph store | Neo4j 5 (Aura) with neosemantics (`n10s`) |
| Orchestration | Docker Compose |

---

## Project structure
```
backend/                # FastAPI server
    main.py            # API routes
    components/        # helper modules (graph, database, NER pipeline, …)
frontend/               # Next.js UI
    app/               # pages (upload, chat, datasets, …)
    public/            # static assets
    package.json        # npm dependencies
datasets/               # example CSV/PDF files
.
.env.example            # template for environment variables
Dockerfile, docker-compose.yml
```

---

## FAQ
* **Do I need to run the NER pipeline manually?** No – the backend runs it automatically for qualifying CSV uploads.
* **Can I see the full Neo4j graph?** Visit the Neo4j Browser at `http://localhost:7474` (username/password from `.env`).
* **How is the chat answer generated?** The LLM receives the user question plus any matching graph nodes, so the answer is grounded in the uploaded medical data.

---

## License
MIT – feel free to adapt and reuse.
