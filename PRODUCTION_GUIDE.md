    🚀 AI HCP CRM — Production System (v2)

🧠 1. System Overview
AI-powered CRM for HCP (Health Care Professionals) with:
- Real-time AI chat (WebSocket)
- LangGraph agent orchestration
- Persistent interaction logging
- Scalable FastAPI backend
- Modern React frontend
- Dockerized deployment

🏗️ 2. Architecture (Clean + Scalable)
[Diagram placeholder]

📦 3. Project Structure (Final)
Frontend:
```
frontend/
├── src/
│   ├── components/
│   │   ├── ChatBox.tsx
│   │   ├── InputArea.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useLocalStorage.ts
│   ├── context/
│   │   ├── ChatContext.tsx
│   ├── services/
│   │   ├── api.ts
│   ├── types/
│   └── main.tsx
```

Backend:
```
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   ├── api/
│   │   ├── routes_chat.py
│   │   ├── routes_hcp.py
│   ├── ws/
│   │   ├── manager.py
│   ├── agents/
│   │   ├── graph.py
│   │   ├── nodes.py
│   │   ├── tools.py
│   ├── db/
│   │   ├── connection.py
│   │   ├── crud.py
│   ├── models/
│   └── schemas/
```

⚙️ 4. Environment Variables
Backend .env:
```
DATABASE_URL=postgresql://user:pass@db:5432/hcp
GROQ_API_KEY=your_key
ENV=production
CORS_ORIGINS=http://localhost:5173
```

Frontend .env:
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws/chat
```

🐳 5. Docker Compose
```yaml
services:
  frontend:
    build: ./frontend
    ports:
      - "5173:5173"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - postgres

  postgres:
    image: postgres:15
    restart: always
    environment:
      POSTGRES_DB: hcp
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

🚀 6. Run Commands
```
# Production
docker compose up --build

# Local Dev
cd backend && uvicorn app.main:app --reload
cd frontend && npm run dev
```

🤖 7. LangGraph Agent Flow
```
Input → Intent → Router → LLM → Tools → Memory → Response
Tools: DB Query, HCP Lookup, Logger
```

🌐 8. APIs
| Method | Endpoint | Auth |
|--------|----------|------|
| GET | /health | No |
| POST | /log | Yes |
| GET | /hcp | Yes |
| WS | /ws/chat | Token |

**Deployment Ready!**

