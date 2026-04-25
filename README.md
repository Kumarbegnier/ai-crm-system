<<<<<<< HEAD

# AI HCP CRM
=======
# Healthcare Professionals CRM
>>>>>>> 04061320 (feat: improve AI CRM agent workflow and documentation)

An AI-powered Customer Relationship Management system for Healthcare Professionals (HCPs) with intelligent conversational agent, rich interaction tracking, and automated data extraction.

<<<<<<< HEAD
## Features
- Real-time WS chat agent (Groq LLM/ollma)
- PostgreSQL HCP/interactions CRUD
- React frontend (dark/typing/memory)
- Docker full stack
=======
## 🌟 Features
>>>>>>> 04061320 (feat: improve AI CRM agent workflow and documentation)

- **AI Chat Agent** — Natural language interface powered by Ollama (llama3) with intent-based routing and structured command execution
- **Rich HCP Profiles** — Track specialty, organization, contact info, location, engagement scores, and custom metadata
- **Intelligent Interaction Logging** — Capture type, channel, sentiment, products discussed, outcomes, and AI-extracted entities
- **Follow-up Management** — Automatic tracking of pending follow-ups with date-based prioritization
- **Tagging & Segmentation** — Flexible tag system with confidence scores and source tracking (LLM/user/system)
- **User Management** — Multi-role support (sales_rep, manager, admin) with territory mapping and activity tracking
- **Metadata Storage** — Key-value store for AI-extracted entities with type inference and confidence scoring
- **Real-time Streaming** — WebSocket-based chat with auto-reconnect and message queueing
- **Dark Mode** — Persistent theme preference with system default detection

## 🛠️ Tech Stack

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS** with custom theme
- **Lucide React** for icons
- **Context API** for state management
- **WebSocket** with exponential backoff reconnect

### Backend
- **Python 3.11**
- **FastAPI** with async/await
- **Gunicorn** + **Uvicorn** workers
- **SQLite** with WAL mode (persistent volume in Docker)
- **Ollama** for local LLM inference
- **Pydantic** for validation

### Infrastructure
- **Docker** & **Docker Compose**
- **Nginx** for frontend static serving (production)

## 🚀 Quick Start

### Prerequisites
- **Docker** and **Docker Compose**
- **Ollama** installed locally ([download](https://ollama.com/download))

### Setup

1. **Pull the llama3 model:**
   ```bash
   ollama pull llama3
   ```

2. **Clone and configure:**
   ```bash
   git clone <repo-url>
   cd ai-hcp-crm
   ```

3. **Update `backend/.env`** (optional — defaults work for local dev):
   ```env
   AGENT_MODEL=llama3
   AGENT_TIMEOUT_SECONDS=30
   SECRET_KEY=your-secret-key-here
   ALLOWED_ORIGINS=http://localhost:3000
   ```

4. **Start the stack:**
   ```bash
   docker compose up --build
   ```

5. **Access:**
   - **Frontend:** http://localhost:3000
   - **API Docs:** http://localhost:8000/docs
   - **Health:** http://localhost:8000/health

## 💻 Local Development (No Docker)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## 🗄️ Database Schema

### Core Tables

**users** — Field reps and managers
- `id`, `name`, `email`, `phone`, `role`, `designation`, `region`, `city`
- `password_hash`, `is_active`, `total_interactions_logged`, `last_active_at`

**hcps** — Healthcare Professionals
- `id`, `name`, `specialty`, `sub_specialty`, `qualification`
- `organization`, `department`, `phone`, `email`
- `city`, `state`, `country`
- `engagement_score`, `total_interactions`, `last_interaction_date`
- `priority` (high/medium/low), `status` (active/inactive)

**interactions** — Rich interaction logs
- `id`, `hcp_id`, `user_id`
- `interaction_type` (call/visit/meeting/email), `interaction_channel`, `interaction_date`
- `notes`, `raw_input`, `ai_summary`, `ai_entities` (JSON)
- `sentiment` (positive/neutral/negative), `product_discussed`, `outcome`
- `follow_up_required`, `follow_up_date`

**interaction_metadata** — Flexible AI storage
- `id`, `interaction_id`, `key`, `value`, `value_type`, `source`, `confidence_score`

**tags** — Segmentation labels
- `id`, `name`, `category`, `description`

**hcp_tags** — HCP ↔ Tag mapping
- `id`, `hcp_id`, `tag_id`, `confidence_score`, `source`

## 🔌 API Endpoints

### HCPs
- `POST /hcp` — Create or update HCP
- `GET /hcp` — List all HCPs
- `GET /hcp/priority/{priority}` — Filter by priority
- `GET /hcp/{name}/profile` — Full profile
- `GET /hcp/{name}` — Interaction history
- `GET /hcp/{name}/tags` — Get HCP tags
- `POST /hcp/{hcp_id}/tags` — Assign tag
- `DELETE /hcp/{hcp_id}/tags/{tag_id}` — Remove tag
- `GET /hcp/by-tag/{tag_name}` — Search by tag

### Interactions
- `POST /log` — Log interaction (supports all fields: type, channel, sentiment, outcome, follow-up, metadata)
- `GET /interactions/followups` — Pending follow-ups
- `DELETE /interaction/{id}` — Delete interaction
- `GET /interaction/{id}/metadata` — Get metadata
- `POST /interaction/{id}/metadata` — Add metadata
- `GET /metadata/search?key=&source=` — Search metadata
- `DELETE /metadata/{id}` — Delete metadata

### Tags
- `POST /tags` — Create tag
- `GET /tags?category=` — List tags
- `DELETE /tags/{id}` — Delete tag

### Users
- `POST /users` — Register user
- `GET /users?role=&region=` — List users
- `GET /users/{id}` — Get user
- `PATCH /users/{id}` — Update user
- `DELETE /users/{id}` — Deactivate user
- `POST /auth/login` — Login

### Agent
- `WebSocket /ws` — Real-time AI chat

## 🤖 AI Agent Actions

The agent understands natural language and routes to 13 structured actions:

| Action | Example Input |
|--------|---------------|
| `CREATE_HCP` | "Register Dr. Smith, cardiologist at Apollo Hospital" |
| `LOG_INTERACTION` | "Met Dr. Patel today, discussed new drug trial, positive outcome" |
| `GET_HCP_HISTORY` | "Show me all interactions with Dr. Kumar" |
| `GET_HCP_PROFILE` | "What's Dr. Singh's profile?" |
| `LIST_HCPS` | "Show all HCPs" |
| `RECOMMEND_HCPS` | "Who should I visit next?" |
| `GET_INACTIVE_HCPS` | "Which HCPs haven't been contacted in 30 days?" |
| `GET_FOLLOWUPS` | "Show pending follow-ups" |
| `FILTER_BY_PRIORITY` | "List high priority HCPs" |
| `CREATE_TAG` | "Create a tag called 'key-opinion-leader'" |
| `ASSIGN_TAG` | "Tag Dr. Sharma as early-adopter" |
| `GET_HCP_TAGS` | "What tags does Dr. Reddy have?" |
| `SEARCH_BY_TAG` | "Find all HCPs tagged as influencer" |

## 🏗️ Architecture

```
┌─────────────┐
│   React     │  ← WebSocket streaming, dark mode, localStorage
│  Frontend   │
└──────┬──────┘
       │ ws://
       ▼
┌─────────────┐
│   FastAPI   │  ← Router/Executor pattern, structured commands
│   Backend   │
└──────┬──────┘
       │
   ┌───┴────┬──────────┐
   ▼        ▼          ▼
┌──────┐ ┌─────┐  ┌────────┐
│SQLite│ │Ollama│ │Gunicorn│
│ WAL  │ │llama3│ │2 workers│
└──────┘ └─────┘  └────────┘
```

<<<<<<< HEAD
## APIs
- POST /log {"hcp_name": "Dr Smith", "notes": "insulin"}
- GET /hcp
- GET /hcp/Dr Neeraj Kumar
- DELETE /interaction/1
=======
## 📊 Key Design Decisions
>>>>>>> 04061320 (feat: improve AI CRM agent workflow and documentation)

1. **SQLite with WAL** — Persistent volume, concurrent reads, 2 workers for write safety
2. **Ollama (local LLM)** — No API costs, full privacy, ~4.7GB model
3. **Router/Executor Split** — Intent detection separated from execution for testability
4. **Metadata Table** — Flexible key-value store for AI-extracted entities instead of rigid columns
5. **PBKDF2 Password Hashing** — 260k iterations with random salt per user
6. **Per-thread Connection Pooling** — SQLite connections reused within each worker thread
7. **Structured Command Schema** — All agent outputs use `{"action": "...", "status": "...", "result": {...}}`

## 🔒 Security Features

<<<<<<< HEAD
Production ready! 🚀
=======
# ai-crm-system
AI-powered Healthcare CRM system for managing HCPs, workflows, automation, and intelligent agent-based interactions.

<img width="1919" height="915" alt="image" src="https://github.com/user-attachments/assets/1b0e7dcf-404f-4d55-b05c-8b3a013515a3" />

=======
- PBKDF2-HMAC-SHA256 password hashing with random salts
- Input validation on all endpoints via Pydantic
- CORS whitelist (configurable via `ALLOWED_ORIGINS`)
- WebSocket message size limit (8 KB)
- SQL injection prevention via parameterized queries
- Prompt injection mitigation (system/user message separation)

## 🚢 Production Deployment

1. **Set a strong `SECRET_KEY`** in `backend/.env`
2. **Update `ALLOWED_ORIGINS`** to your production domain
3. **Scale workers** — keep `WEB_CONCURRENCY=2` for SQLite; migrate to PostgreSQL if you need >2
4. **Enable HTTPS** — add a reverse proxy (nginx/Caddy) in front of the stack
5. **Backup** — the SQLite DB is in the `sqlite_data` Docker volume; back it up regularly

## 📝 Example Usage

### Via Chat UI
```
User: Met Dr. Sharma today, discussed Lipitor, very interested, follow up next week
Agent: ✅ Logged interaction for Dr. Sharma (ID: 42)

User: Who needs follow-up?
Agent: 🔔 Pending Follow-ups (3):
       • Dr. Sharma — call
         Discussed Lipitor, very interested
         💊 Lipitor
         📌 interested
         🔔 Due: 2024-01-15
       ...
```

### Via REST API
```bash
# Log an interaction
curl -X POST http://localhost:8000/log \
  -H "Content-Type: application/json" \
  -d '{
    "hcp_name": "Dr. Sharma",
    "notes": "Discussed new drug trial",
    "interaction_type": "visit",
    "sentiment": "positive",
    "product_discussed": "Lipitor",
    "outcome": "interested",
    "follow_up_required": true,
    "follow_up_date": "2024-01-15"
  }'

# Get HCP profile
curl http://localhost:8000/hcp/Dr.%20Sharma/profile
```

## 🧪 Testing

```bash
cd frontend
npm test              # Run tests
npm run test:ui       # Interactive test UI
npm run test:coverage # Coverage report
```

## 📚 Project Structure

```
ai-hcp-crm/
├── backend/
│   ├── app/
│   │   ├── routers/          # Modular route handlers
│   │   │   ├── hcp.py
│   │   │   ├── interactions.py
│   │   │   ├── tags.py
│   │   │   ├── users.py
│   │   │   └── validators.py
│   │   ├── agent.py          # LLM router + executor
│   │   ├── config.py         # Centralized config
│   │   ├── db.py             # Connection pooling + init
│   │   ├── db_utils.py       # All DB queries
│   │   └── main.py           # FastAPI app orchestrator
│   ├── .env
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatBox/
│   │   │   └── InputArea/
│   │   ├── contexts/
│   │   │   └── ChatContext.tsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   └── useLocalStorage.ts
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── setup_db.sql          # PostgreSQL schema (reference only)
└── README.md

```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `npm test` (frontend), `pytest` (backend)
4. Submit a pull request

## 📄 License

MIT License — see LICENSE file for details

---

**Built for production. Optimized for speed. Powered by AI.** 🚀
>>>>>>> 04061320 (feat: improve AI CRM agent workflow and documentation)
