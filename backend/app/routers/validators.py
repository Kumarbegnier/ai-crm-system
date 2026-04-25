"""Shared Pydantic field validators reused across request models."""
from typing import Optional


def validate_source(v: Optional[str]) -> Optional[str]:
    allowed = ("llm", "user", "system")
    if v and v.lower() not in allowed:
        raise ValueError(f"source must be one of {allowed}")
    return v.lower() if v else None  # None lets the field default take effect


def validate_confidence(v: Optional[float]) -> Optional[float]:
    if v is not None and not (0.0 <= v <= 1.0):
        raise ValueError("confidence_score must be between 0 and 1")
    return v
