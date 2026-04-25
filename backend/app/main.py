import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import ALLOWED_ORIGINS
from .db import init_db
from .agent import run_agent_stream
from .llm_client import get_client
from .vector_store import get_vector_store
from .routers import hcp, interactions, tags, users, appointments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

WS_MAX_MESSAGE_BYTES = 8_192


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    await asyncio.to_thread(init_db)
    logger.info("Database ready.")
    logger.info("Rebuilding vector store...")
    try:
        get_vector_store().rebuild_from_db()
        logger.info("Vector store ready.")
    except Exception as e:
        logger.warning(f"Vector store init failed (non-critical): {e}")
    try:
        await get_client().list()
        logger.info("Ollama connection verified.")
    except Exception as e:
        logger.warning(f"Ollama not reachable at startup: {e}")
    yield
    logger.info("Shutting down.")


app = FastAPI(title="Healthcare Professionals CRM", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(hcp.router)
app.include_router(interactions.router)
app.include_router(tags.router)
app.include_router(users.router)
app.include_router(appointments.router)


@app.get("/")
async def home():
    return {"message": "Healthcare Professionals CRM 🏥"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Use client address + random suffix as session ID for memory isolation
    session_id = f"{websocket.client.host}:{websocket.client.port}"
    logger.info(f"WebSocket connected [session={session_id}]")
    try:
        while True:
            user_input = await websocket.receive_text()
            if len(user_input.encode()) > WS_MAX_MESSAGE_BYTES:
                await websocket.send_text("⚠️ Message too large. Please keep it under 8 KB.")
                continue
            if not user_input.strip():
                continue
            async for chunk in run_agent_stream(user_input, session_id=session_id):
                await websocket.send_text(chunk)
            await websocket.send_text("__END__")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected [session={session_id}]")
