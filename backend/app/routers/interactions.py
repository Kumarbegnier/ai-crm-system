import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from ..db_utils import (
    insert_interaction, delete_interaction, get_pending_followups,
    get_metadata_by_interaction, upsert_metadata, get_metadata_by_key, delete_metadata,
    get_daily_summary,
)
from .validators import validate_source, validate_confidence

router = APIRouter(tags=["Interactions"])
logger = logging.getLogger(__name__)


class InteractionRequest(BaseModel):
    hcp_name: str
    notes: str
    interaction_type: Optional[str] = "call"
    interaction_channel: Optional[str] = None
    interaction_date: Optional[str] = None
    raw_input: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_entities: Optional[dict] = None
    sentiment: Optional[str] = None
    product_discussed: Optional[str] = None
    outcome: Optional[str] = None
    follow_up_required: Optional[bool] = False
    follow_up_date: Optional[str] = None
    user_id: Optional[int] = None
    metadata: Optional[list] = None

    @field_validator("hcp_name")
    @classmethod
    def hcp_name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("hcp_name must not be empty")
        return v

    @field_validator("notes")
    @classmethod
    def notes_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("notes must not be empty")
        return v

    @field_validator("interaction_type")
    @classmethod
    def valid_type(cls, v: Optional[str]) -> Optional[str]:
        allowed = ("call", "visit", "meeting", "email")
        if v and v.lower() not in allowed:
            raise ValueError(f"interaction_type must be one of {allowed}")
        return v.lower() if v else "call"

    @field_validator("sentiment")
    @classmethod
    def valid_sentiment(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ("positive", "neutral", "negative"):
            raise ValueError("sentiment must be positive, neutral, or negative")
        return v.lower() if v else None

    @field_validator("outcome")
    @classmethod
    def valid_outcome(cls, v: Optional[str]) -> Optional[str]:
        allowed = ("interested", "not_interested", "follow_up_required")
        if v and v.lower() not in allowed:
            raise ValueError(f"outcome must be one of {allowed}")
        return v.lower() if v else None


class MetadataRequest(BaseModel):
    key: str
    value: str
    value_type: Optional[str] = "string"
    source: Optional[str] = "user"
    confidence_score: Optional[float] = None

    @field_validator("key")
    @classmethod
    def key_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("key must not be empty")
        return v

    @field_validator("value_type")
    @classmethod
    def valid_value_type(cls, v: Optional[str]) -> Optional[str]:
        allowed = ("string", "number", "date", "boolean", "json")
        if v and v.lower() not in allowed:
            raise ValueError(f"value_type must be one of {allowed}")
        return v.lower() if v else "string"

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: Optional[str]) -> Optional[str]:
        return validate_source(v)

    @field_validator("confidence_score")
    @classmethod
    def valid_confidence(cls, v: Optional[float]) -> Optional[float]:
        return validate_confidence(v)


@router.post("/log", status_code=201)
async def log_interaction(req: InteractionRequest):
    interaction_id = await asyncio.to_thread(
        insert_interaction,
        req.hcp_name, req.notes,
        req.interaction_type or "call",
        req.interaction_channel, req.interaction_date,
        req.raw_input, req.ai_summary, req.ai_entities,
        req.sentiment, req.product_discussed, req.outcome,
        req.follow_up_required or False, req.follow_up_date,
        req.user_id, req.metadata,
    )
    logger.info(f"Logged interaction {interaction_id} for '{req.hcp_name}'")
    return {"status": "saved", "interaction_id": interaction_id}


@router.get("/interactions/followups")
async def pending_followups():
    return {"followups": await asyncio.to_thread(get_pending_followups)}


@router.get("/interactions/summary")
async def daily_summary():
    """Today's performance summary: visits, interactions, top HCP, segment insight."""
    return {"summary": await asyncio.to_thread(get_daily_summary)}


@router.delete("/interaction/{interaction_id}")
async def delete(interaction_id: int):
    if not await asyncio.to_thread(delete_interaction, interaction_id):
        raise HTTPException(404, detail=f"Interaction {interaction_id} not found")
    return {"status": "deleted"}


@router.get("/interaction/{interaction_id}/metadata")
async def get_interaction_metadata(interaction_id: int):
    return {"metadata": await asyncio.to_thread(get_metadata_by_interaction, interaction_id)}


@router.post("/interaction/{interaction_id}/metadata", status_code=201)
async def add_metadata(interaction_id: int, req: MetadataRequest):
    metadata_id = await asyncio.to_thread(
        upsert_metadata, interaction_id, req.key, req.value,
        req.value_type or "string", req.source or "user", req.confidence_score,
    )
    return {"status": "saved", "metadata_id": metadata_id}


@router.get("/metadata/search")
async def search_metadata(key: str, source: Optional[str] = None):
    results = await asyncio.to_thread(get_metadata_by_key, key, source)
    if not results:
        raise HTTPException(404, detail=f"No metadata found for key '{key}'")
    return {"results": results}


@router.delete("/metadata/{metadata_id}")
async def remove_metadata(metadata_id: int):
    if not await asyncio.to_thread(delete_metadata, metadata_id):
        raise HTTPException(404, detail=f"Metadata {metadata_id} not found")
    return {"status": "deleted"}
