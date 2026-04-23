from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .db_utils import (
    insert_interaction,
    get_all_hcp,
    get_interactions_by_hcp,
    delete_interaction
)
from .agent import run_agent_stream

app = FastAPI(title="AI HCP CRM")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InteractionRequest(BaseModel):
    hcp_name: str
    notes: str

@app.get("/")
async def home():
    return {"message": "AI HCP CRM Backend 🚀"}

@app.post("/log")
async def log_interaction(req: InteractionRequest):
    insert_interaction(req.hcp_name, req.notes)
    return {"status": "saved"}

@app.get("/hcp")
async def list_hcp():
    return {"hcp": get_all_hcp()}

@app.get("/hcp/{name}")
async def get_hcp_history(name: str):
    return {"history": get_interactions_by_hcp(name)}

@app.delete("/interaction/{interaction_id}")
async def delete(interaction_id: int):
    delete_interaction(interaction_id)
    return {"status": "deleted"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        user_input = await websocket.receive_text()
        async for chunk in run_agent_stream(user_input):
            await websocket.send_text(chunk)

