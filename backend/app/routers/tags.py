import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from ..db_utils import upsert_tag, get_all_tags, delete_tag

router = APIRouter(prefix="/tags", tags=["Tags"])


class TagRequest(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v


@router.post("", status_code=201)
async def create_tag(req: TagRequest):
    tag_id = await asyncio.to_thread(upsert_tag, req.name, req.category, req.description)
    return {"status": "saved", "tag_id": tag_id}


@router.get("")
async def list_tags(category: Optional[str] = None):
    return {"tags": await asyncio.to_thread(get_all_tags, category)}


@router.delete("/{tag_id}")
async def remove_tag(tag_id: int):
    if not await asyncio.to_thread(delete_tag, tag_id):
        raise HTTPException(404, detail=f"Tag {tag_id} not found")
    return {"status": "deleted"}
