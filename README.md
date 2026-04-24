
# AI HCP CRM

Production AI-powered Healthcare Professional CRM.

## Features
- Real-time WS chat agent (Groq LLM)
- PostgreSQL HCP/interactions CRUD
- React frontend (dark/typing/memory)
- Docker full stack

## Quick Start
1. Update `.env` (DB_PASSWORD, GROQ_API_KEY)
2. `docker compose up --build`
3. Backend: http://localhost:8000/docs
4. Frontend: http://localhost:3000
5. Chat: localhost:3000 (WS → /ws)

## Local Dev
**Backend:**
```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```
cd frontend
npm install
npm run dev
```

## DB Schema
```
hcp (id, name)
interactions (id, hcp_id, notes, created_at)
```

## APIs
- POST /log {"hcp_name": "Dr Smith", "notes": "insulin"}
- GET /hcp
- GET /hcp/Dr Smith
- DELETE /interaction/1

Agent tools auto-triggered by chat.

## Docker
`docker compose down -v ; docker compose up --build`

Production ready! 🚀
=======
# ai-crm-system
AI-powered Healthcare CRM system for managing HCPs, workflows, automation, and intelligent agent-based interactions.

<img width="1919" height="915" alt="image" src="https://github.com/user-attachments/assets/1b0e7dcf-404f-4d55-b05c-8b3a013515a3" />

