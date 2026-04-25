import asyncio
import sqlite3
from typing import Optional
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, field_validator
from ..db_utils import (
    create_user, get_user_by_id, get_all_users,
    update_user, verify_user_password, deactivate_user, VALID_ROLES,
)
from ..auth import create_access_token

router = APIRouter(tags=["Users"])


class UserRequest(BaseModel):
    name: str
    email: str
    password: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = "sales_rep"
    designation: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("email")
    @classmethod
    def email_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if not v or "@" not in v:
            raise ValueError("valid email is required")
        return v

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v.lower() if v else "sales_rep"


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    designation: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def valid_role(cls, v: Optional[str]) -> Optional[str]:
        if v and v.lower() not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v.lower() if v else None


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/auth/signup", status_code=201)
async def signup(req: UserRequest):
    """Register a new user and return a JWT token."""
    try:
        user_id = await asyncio.to_thread(create_user, req.model_dump(exclude_none=True))
        token = create_access_token({"sub": str(user_id), "email": req.email, "role": req.role or "sales_rep"})
        return {"status": "created", "user_id": user_id, "token": token}
    except sqlite3.IntegrityError:
        raise HTTPException(409, detail="Email already registered")
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@router.post("/users", status_code=201)
async def register_user(req: UserRequest):
    try:
        user_id = await asyncio.to_thread(create_user, req.model_dump(exclude_none=True))
        return {"status": "created", "user_id": user_id}
    except sqlite3.IntegrityError:
        raise HTTPException(409, detail="Email already registered")
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@router.get("/users")
async def list_users(role: Optional[str] = None, region: Optional[str] = None):
    return {"users": await asyncio.to_thread(get_all_users, role, region)}


@router.get("/users/{user_id}")
async def get_user(user_id: int = Path(..., gt=0)):
    user = await asyncio.to_thread(get_user_by_id, user_id)
    if not user:
        raise HTTPException(404, detail=f"User {user_id} not found")
    return {"user": user}


@router.patch("/users/{user_id}")
async def patch_user(user_id: int = Path(..., gt=0), req: UserUpdateRequest = ...):
    if not await asyncio.to_thread(update_user, user_id, req.model_dump(exclude_none=True)):
        raise HTTPException(404, detail=f"User {user_id} not found")
    return {"status": "updated"}


@router.delete("/users/{user_id}")
async def deactivate(user_id: int = Path(..., gt=0)):
    if not await asyncio.to_thread(deactivate_user, user_id):
        raise HTTPException(404, detail=f"User {user_id} not found")
    return {"status": "deactivated"}


@router.post("/auth/login")
async def login(req: LoginRequest):
    user = await asyncio.to_thread(verify_user_password, req.email, req.password)
    if not user:
        raise HTTPException(401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user["id"]), "email": user["email"], "role": user["role"]})
    return {"status": "ok", "token": token, "user": user}
