# AI Closer

AI Closer is a FastAPI + LangGraph CRM and meeting intelligence web app for sales teams. It stores clients and meetings in SQL, analyzes transcripts with Llama 3.1 8B through Ollama or Groq, and shows sentiment, deal probability, objections, pain points, recommendations, next actions, and client history in a clean internal SaaS interface.

## Stack

- Backend: Python, FastAPI, SQLAlchemy ORM, LangGraph
- Database: SQLite by default, PostgreSQL-ready through `DATABASE_URL`
- LLM: Llama 3.1 8B via Ollama or Groq
- Frontend: static HTML, CSS, and vanilla JavaScript
- Export: PDF meeting reports through ReportLab

## Project Structure

```text
backend/
  app/
    api/
    agents/
    workflows/
    services/
    database/
    models/
    schemas/
    prompts/
    utils/
    main.py
  alembic/
  requirements.txt
  .env.example
frontend/
  pages/
  css/
  js/
  assets/
```

## Installation

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Running the Backend and Frontend

The FastAPI server also serves the static frontend.

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

- Login: `http://127.0.0.1:8000/login`
- Dashboard: `http://127.0.0.1:8000/`
- Add client: `http://127.0.0.1:8000/add-client`
- API docs: `http://127.0.0.1:8000/docs`

## Starter Login Accounts

The app seeds these 10 accounts on startup if they do not already exist. Passwords are stored as hashes in the database.

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `admin123` | admin |
| `samy` | `samy123` | staff |
| `ahmed` | `ahmed123` | staff |
| `sales1` | `sales123` | staff |
| `sales2` | `sales223` | staff |
| `closer1` | `closer123` | staff |
| `closer2` | `closer223` | staff |
| `manager` | `manager123` | admin |
| `ops` | `ops123` | staff |
| `demo` | `demo123` | staff |

Clients, meetings, and follow-ups are scoped to the logged-in user. Admins can manage users through the API:

- `POST /auth/login`
- `POST /auth/logout`
- `GET /auth/me`
- `GET /users`
- `POST /users`
- `PUT /users/{id}`

## Ollama Setup

Install Ollama, then pull and run Llama 3.1 8B:

```bash
ollama pull llama3.1:8b
ollama serve
```

Use these `.env` values:

```env
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
```

## Groq Setup

Set your Groq API key in `backend/.env`:

```env
LLM_PROVIDER=groq
LLM_MODEL=llama-3.1-8b-instant
GROQ_API_KEY=your_key_here
```

## Local Demo Mode

For demos without Ollama or Groq, use:

```env
LLM_PROVIDER=mock
```

The mock provider keeps the app runnable but is not a replacement for Llama analysis.

## Database Migrations

For local development, the app creates SQLite tables on startup. To run the included Alembic migration explicitly:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

To use PostgreSQL, install the PostgreSQL driver you prefer, then set:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/ai_closer
```

## Running the LangGraph Workflow

The workflow runs automatically when `POST /meetings/process` is called. It executes these nodes in order:

1. Transcript Cleaner Agent
2. Speaker Detection Agent
3. Sentiment Analysis Agent
4. Objection Extraction Agent
5. Deal Acceptance Prediction Agent
6. Recommendation Agent
7. Summary Agent
8. Final Report Generator Agent

Example API call:

```bash
curl -X POST http://127.0.0.1:8000/meetings/process \
  -H "Content-Type: application/json" \
  -d '{
    "client_name": "Acme Corp",
    "phone": "+1 555 0100",
    "meeting_date": "2026-05-22",
    "transcript": "Sales: What are you trying to improve? Client: We lose time with manual follow ups and want to start soon, but price is a concern."
  }'
```

## Main API Endpoints

- `GET /clients`
- `POST /clients`
- `GET /clients/{id}`
- `PUT /clients/{id}`
- `DELETE /clients/{id}`
- `POST /meetings/process`
- `GET /meetings/{id}`
- `GET /clients/{id}/meetings`
- `GET /search?q=`
- `GET /analytics/summary`
- `GET /meetings/{id}/export.pdf`
