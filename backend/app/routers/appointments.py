import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from ..db_utils import (
    get_hcp_profile,
    create_appointment,
    is_available,
    get_appointments,
    suggest_alternatives,
    cancel_appointment,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Appointments"])


class BookAppointmentRequest(BaseModel):
    doctor_name: str
    date: str
    time: str
    notes: Optional[str] = None

    @field_validator("doctor_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("doctor_name must not be empty")
        return v

    @field_validator("date")
    @classmethod
    def date_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("date must not be empty")
        return v

    @field_validator("time")
    @classmethod
    def time_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("time must not be empty")
        return v


class CancelAppointmentRequest(BaseModel):
    appointment_id: int


@router.post("/appointments/book", status_code=201)
async def book_appointment(req: BookAppointmentRequest):
    hcp = await asyncio.to_thread(get_hcp_profile, req.doctor_name)
    if not hcp:
        # Auto-create HCP if not found
        from ..db_utils import upsert_hcp
        hcp_id = await asyncio.to_thread(upsert_hcp, {"name": req.doctor_name})
        hcp = {"id": hcp_id, "name": req.doctor_name}

    available = await asyncio.to_thread(is_available, hcp["id"], req.date, req.time)
    if not available:
        alts = await asyncio.to_thread(suggest_alternatives, hcp["id"], req.date, req.time)
        raise HTTPException(
            409,
            detail={
                "message": f"Dr. {req.doctor_name} is not available at {req.time} on {req.date}.",
                "alternatives": alts,
            }
        )

    appointment_id = await asyncio.to_thread(
        create_appointment, hcp["id"], req.date, req.time, req.notes
    )
    logger.info(f"Appointment booked: {appointment_id} for {req.doctor_name}")
    return {
        "status": "booked",
        "appointment_id": appointment_id,
        "doctor": req.doctor_name,
        "date": req.date,
        "time": req.time,
    }


@router.get("/appointments")
async def list_appointments(
    doctor_name: Optional[str] = None,
    date: Optional[str] = None,
    status: Optional[str] = None,
):
    return {
        "appointments": await asyncio.to_thread(
            get_appointments, doctor_name, date, status
        )
    }


@router.get("/appointments/available/{doctor_name}/{date}")
async def available_slots(doctor_name: str, date: str):
    hcp = await asyncio.to_thread(get_hcp_profile, doctor_name)
    if not hcp:
        raise HTTPException(404, detail=f"Doctor '{doctor_name}' not found")

    # Generate all slots 09:00-17:00 every 30 min
    all_slots = []
    hour, minute = 9, 0
    while hour < 17:
        all_slots.append(f"{hour:02d}:{minute:02d}")
        minute += 30
        if minute >= 60:
            minute = 0
            hour += 1

    taken = set()
    appointments = await asyncio.to_thread(get_appointments, doctor_name, date, "scheduled")
    for appt in appointments:
        taken.add(appt["time"])

    available = [s for s in all_slots if s not in taken]
    return {"doctor": doctor_name, "date": date, "available_slots": available}


@router.delete("/appointments/{appointment_id}")
async def delete_appointment(appointment_id: int):
    if not await asyncio.to_thread(cancel_appointment, appointment_id):
        raise HTTPException(404, detail=f"Appointment {appointment_id} not found")
    return {"status": "cancelled"}

