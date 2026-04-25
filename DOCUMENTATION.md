# AI HCP CRM Documentation

## Architecture
```
Frontend (Vite + React 18 + TS + Tailwind)
  ├── Components (ChatBox, InputArea)
  ├── Hooks (useWebSocket, useLocalStorage)
  ├── Context (ChatContext zustand)
  └── Docker

Backend (FastAPI + PostgreSQL + LangGraph)
  ├── APIs (WS /chat, CRUD /hcp)
  ├── Agent (Groq LLM + Tools)
  ├── DB (asyncpg CRUD)
  └── Docker

Docker Compose (Postgres + Backend + Frontend)
```

## Setup
1. `docker compose up --build` (production)
2. Local:
   ```
   cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
   cd frontend && npm install && npm run dev
   ```

## Features
- Real-time WS chat
- HCP interaction logging
- LocalStorage persistence
- Dark mode
- Responsive UI
- LLM agent tools

## APIs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Health |
| POST | /log | Log HCP interaction |
| GET | /hcp | List HCPs |
| GET | /hcp/{name} | HCP history |
| DELETE | /interaction/{id} | Delete |

## Testing
`npm test` (Vitest + RTL + jsdom) 5/5 pass

## Production
- Docker multi-stage
- Nginx reverse proxy
- Postgres persistent vol

## Tech Stack
- React 18 TS
- Vite 5
- Tailwind 3.4
- Vitest 1
- FastAPI 0.104
- asyncpg
- Groq/LangGraph

**Ready for deployment!**

