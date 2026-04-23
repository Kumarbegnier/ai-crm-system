# Backend Setup TODO - Simple NO-AI FastAPI + PostgreSQL

## Current Status: Backend code complete ✅

### Phase 1: Code Updates ✅
- [x] Create this TODO.md
- [x] Update backend/requirements.txt (add psycopg2-binary, remove extras)
- [x] Update backend/db_utils.py to exact task code (simple insert/get/delete)
- [x] Replace backend/main.py with task FastAPI CRUD
- [x] Ignore/ del backend/agent.py optional (not used)
- [x] Create backend/.env with task vars (update DB_PASSWORD)

### Phase 2: Dependencies & Run
- [ ] cd backend
- [ ] venv\Scripts\activate (Windows)
- [ ] pip install -r requirements.txt
- [ ] uvicorn main:app --reload

### Phase 3: Database Setup (PostgreSQL)
- [ ] Verify psql: `psql --version`
- [ ] `createdb crm_ai` or psql "CREATE DATABASE crm_ai;"
- [ ] psql -d crm_ai -c "CREATE TABLE hcp (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE NOT NULL);"
- [ ] psql -d crm_ai -c "CREATE TABLE interactions (id SERIAL PRIMARY KEY, hcp_id INT REFERENCES hcp(id) ON DELETE CASCADE, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"

### Phase 4: Test
- [ ] Visit http://127.0.0.1:8000/docs
- [ ] POST /log {"hcp_name": "Dr Sharma", "notes": "Discussed insulin"}
- [ ] GET /hcp
- [ ] GET /hcp/Dr%20Sharma
- [ ] DELETE /interaction/1

**Backend fully ready! Update password in .env. Ping for DB help if psql issues.**


### Phase 2: Dependencies & Run
- [ ] cd backend
- [ ] venv\Scripts\activate (Windows)
- [ ] pip install -r requirements.txt
- [ ] uvicorn main:app --reload

### Phase 3: Database Setup (PostgreSQL)
- [ ] Verify psql: `psql --version`
- [ ] CREATE DATABASE crm_ai;
- [ ] \c crm_ai;
- [ ] CREATE TABLE hcp (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE NOT NULL);
- [ ] CREATE TABLE interactions (id SERIAL PRIMARY KEY, hcp_id INT REFERENCES hcp(id) ON DELETE CASCADE, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

### Phase 4: Test
- [ ] Visit http://127.0.0.1:8000/docs
- [ ] POST /log { "hcp_name": "Dr Sharma", "notes": "Test" }
- [ ] GET /hcp
- [ ] GET /hcp/Dr Sharma
- [ ] DELETE /interaction/1

**Mark as [x] when complete. Ping if errors.**


### Phase 2: Dependencies & Run
- [ ] cd backend
- [ ] venv\Scripts\activate (Windows)
- [ ] pip install -r requirements.txt
- [ ] uvicorn main:app --reload

### Phase 3: Database Setup (PostgreSQL)
- [ ] Verify psql: `psql --version`
- [ ] CREATE DATABASE crm_ai;
- [ ] \c crm_ai;
- [ ] CREATE TABLE hcp (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE NOT NULL);
- [ ] CREATE TABLE interactions (id SERIAL PRIMARY KEY, hcp_id INT REFERENCES hcp(id) ON DELETE CASCADE, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);

### Phase 4: Test
- [ ] Visit http://127.0.0.1:8000/docs
- [ ] POST /log { "hcp_name": "Dr Sharma", "notes": "Test" }
- [ ] GET /hcp
- [ ] GET /hcp/Dr Sharma
- [ ] DELETE /interaction/1

**Mark as [x] when complete. Ping if errors.**

