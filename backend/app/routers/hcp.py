import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from ..db_utils import (
    upsert_hcp, get_hcp_profile, get_all_hcp,
    get_interactions_by_hcp, get_hcps_by_priority,
    assign_tag_to_hcp, remove_tag_from_hcp, get_hcp_tags, get_hcps_by_tag,
)
from .validators import validate_confidence, validate_source

router = APIRouter(prefix="/hcp", tags=["HCPs"])


class HCPRequest(BaseModel):
    name: str
    specialty: Optional[str] = None
    sub_specialty: Optional[str] = None
    qualification: Optional[str] = None
    organization: Optional[str] = None
    department: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "India"
    priority: Optional[str] = "medium"
    status: Optional[str] = "active"
    created_by: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("priority")
    @classmethod
    def valid_priority(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in ("high", "medium", "low"):
            raise ValueError("priority must be high, medium, or low")
        return v.lower() if v else "medium"


class AssignTagRequest(BaseModel):
    tag_id: int
    confidence_score: Optional[float] = None
    source: Optional[str] = "user"

    @field_validator("source")
    @classmethod
    def valid_source(cls, v: Optional[str]) -> Optional[str]:
        return validate_source(v)

    @field_validator("confidence_score")
    @classmethod
    def valid_confidence(cls, v: Optional[float]) -> Optional[float]:
        return validate_confidence(v)


@router.post("", status_code=201)
async def create_or_update_hcp(req: HCPRequest):
    hcp_id = await asyncio.to_thread(upsert_hcp, req.model_dump(exclude_none=True))
    return {"status": "saved", "hcp_id": hcp_id}


@router.get("")
async def list_hcp():
    return {"hcp": await asyncio.to_thread(get_all_hcp)}


@router.get("/priority/{priority}")
async def hcp_by_priority(priority: str):
    hcps = await asyncio.to_thread(get_hcps_by_priority, priority)
    if not hcps:
        raise HTTPException(404, detail=f"No active HCPs with priority '{priority}'")
    return {"hcp": hcps}


@router.get("/by-tag/{tag_name}")
async def hcps_by_tag(tag_name: str):
    hcps = await asyncio.to_thread(get_hcps_by_tag, tag_name)
    if not hcps:
        raise HTTPException(404, detail=f"No HCPs found with tag '{tag_name}'")
    return {"tag": tag_name, "hcp": hcps}


# Sub-paths of /{name} MUST be registered before /{name} itself
@router.get("/{name}/profile")
async def get_hcp_full_profile(name: str):
    profile = await asyncio.to_thread(get_hcp_profile, name)
    if not profile:
        raise HTTPException(404, detail=f"HCP '{name}' not found")
    return {"profile": profile}


@router.get("/{name}/tags")
async def hcp_tags(name: str):
    return {"hcp_name": name, "tags": await asyncio.to_thread(get_hcp_tags, name)}


# Wildcard /{name} must come LAST among GET routes
@router.get("/{name}")
async def get_hcp_history(name: str):
    history = await asyncio.to_thread(get_interactions_by_hcp, name)
    if not history:
        raise HTTPException(404, detail=f"No interactions found for '{name}'")
    return {"history": history}


@router.post("/{hcp_id}/tags", status_code=201)
async def add_tag_to_hcp(hcp_id: int, req: AssignTagRequest):
    assigned = await asyncio.to_thread(
        assign_tag_to_hcp, hcp_id, req.tag_id, req.confidence_score, req.source or "user"
    )
    if not assigned:
        raise HTTPException(409, detail="Tag already assigned to this HCP")
    return {"status": "assigned"}


@router.delete("/{hcp_id}/tags/{tag_id}")
async def delete_tag_from_hcp(hcp_id: int, tag_id: int):
    removed = await asyncio.to_thread(remove_tag_from_hcp, hcp_id, tag_id)
    if not removed:
        raise HTTPException(404, detail="Tag assignment not found")
    return {"status": "removed"}
