# AI News

> Work in progress.

Collects AI news from RSS feeds and summarizes long articles in Turkish with the Gemini API,
using a rate-limited summarization queue. Built with FastAPI + SQLModel and Vue 3 + TypeScript.

See [`docs/PLAN.md`](docs/PLAN.md) for the architecture and roadmap.

## Frontend (development)

Requires Node.js ^22.18 and npm 11.

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173 (start the backend first)
```

## Backend (development)

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd backend
cp .env.example .env      # then fill in the values
uv sync                   # create .venv and install dependencies
uv run fastapi dev        # http://localhost:8000/docs
uv run pytest             # tests
```
