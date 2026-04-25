"""
LangGraph-inspired AI Agent for Healthcare CRM.

Implements a state-machine with session memory:
  Input → Intent Classification → Node Routing → State Updates → Response

Nodes:
  - intent_classifier: determines intent from user input + session context
  - appointment_node: multi-step booking (doctor → date → time → confirm)
  - interaction_node: log interactions with auto-extraction
  - recommendation_node: AI-scored HCP recommendations
  - followup_node: pending follow-ups
  - summary_node: daily summary
  - search_node: semantic search over interaction notes
  - email_node: generate follow-up emails
  - response_node: natural language fallback via LLM

Session memory is stored per WebSocket connection ID with TTL cleanup.
"""

import re
import json
import logging
import asyncio
import time
from datetime import datetime, timedelta
from .config import AGENT_MODEL, AGENT_TIMEOUT
from .llm_client import get_client
from .db_utils import (
    insert_interaction,
    get_interactions_by_hcp,
    get_all_hcp,
    get_inactive_hcps,
    recommend_hcps,
    upsert_hcp,
    get_hcp_profile,
    get_hcps_by_priority,
    get_pending_followups,
    get_daily_summary,
    upsert_tag,
    get_tag_by_name,
    assign_tag_to_hcp,
    get_hcp_tags,
    get_hcps_by_tag,
    is_available,
    create_appointment,
    suggest_alternatives,
    get_appointments,
    get_appointment_by_id,
    cancel_appointment,
    normalize_name,
)
from .ai_tools import generate_ai_summary, generate_followup_email, extract_entities_from_notes
from .vector_store import get_vector_store

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
_ROUTER_TIMEOUT = max(10, AGENT_TIMEOUT // 2)

# ---------------------------------------------------------------------------
# Session Memory (Critical)
# ---------------------------------------------------------------------------
# session_id → {intent, doctor, date, time, step, history, last_active}
_SESSIONS: dict[str, dict] = {}
_SESSION_TTL_SECONDS = 600  # 10 minutes


def _get_session(session_id: str) -> dict:
    """Get or create a session."""
    now = time.time()
    if session_id in _SESSIONS:
        _SESSIONS[session_id]["last_active"] = now
        return _SESSIONS[session_id]
    _SESSIONS[session_id] = {
        "intent": None,
        "doctor": None,
        "date": None,
        "time": None,
        "step": "identify_intent",
        "history": [],
        "last_active": now,
    }
    return _SESSIONS[session_id]


def _clear_session(session_id: str):
    _SESSIONS.pop(session_id, None)


def _cleanup_sessions():
    """Remove stale sessions."""
    now = time.time()
    stale = [sid for sid, s in _SESSIONS.items() if now - s["last_active"] > _SESSION_TTL_SECONDS]
    for sid in stale:
        _SESSIONS.pop(sid, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    match = _JSON_FENCE_RE.search(text)
    candidate = match.group(1) if match else None
    if not candidate:
        start, end = text.find('{'), text.rfind('}') + 1
        candidate = text[start:end] if start != -1 else None
    if not candidate:
        return {}
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return {}


def _ok(action: str, params: dict, result: dict, confidence: float = 1.0, reason: str = "") -> str:
    return json.dumps({
        "action": action,
        "status": "ok",
        "params": params,
        "result": result,
        "tool_used": action,
        "confidence": confidence,
        "reason": reason or f"Executed {action.lower().replace('_', ' ')}",
    }, default=str)


def _err(action: str, message: str, confidence: float = 1.0, reason: str = "") -> str:
    return json.dumps({
        "action": action,
        "status": "error",
        "result": {"message": message},
        "tool_used": action,
        "confidence": confidence,
        "reason": reason or f"Failed to execute {action.lower().replace('_', ' ')}",
    }, default=str)


def _ask(action: str, question: str, confidence: float = 1.0, reason: str = "") -> str:
    return json.dumps({
        "action": action,
        "status": "ask",
        "result": {"message": question},
        "tool_used": action,
        "confidence": confidence,
        "reason": reason or f"Need more info for {action.lower().replace('_', ' ')}",
    }, default=str)


# ---------------------------------------------------------------------------
# Anaphora Resolution (Multi-turn pronouns)
# ---------------------------------------------------------------------------
_ANAPHORA_RE = re.compile(r'\b(his|her|their|they|him|she|he)\b', re.IGNORECASE)


def _resolve_anaphora(user_input: str, session: dict) -> str:
    """
    Replace pronouns like 'his', 'her', 'they' with the last mentioned doctor
    if one exists in session context.
    """
    last_doctor = session.get("doctor")
    if not last_doctor:
        return user_input

    if _ANAPHORA_RE.search(user_input):
        # Replace pronouns with the doctor's name
        resolved = _ANAPHORA_RE.sub(last_doctor, user_input)
        logger.info(f"Anaphora resolved: '{user_input}' → '{resolved}'")
        return resolved
    return user_input


# ---------------------------------------------------------------------------
# Tool Parameter Validation
# ---------------------------------------------------------------------------

def _validate_tool_params(action: str, params: dict) -> tuple[bool, str]:
    """
    Validate required parameters before executing a tool.
    Returns (is_valid, error_message).
    """
    required = {
        "BOOK_APPOINTMENT": ["doctor", "date", "time"],
        "LOG_INTERACTION": ["hcp_name"],
        "GET_HCP_HISTORY": ["hcp_name"],
        "GET_HCP_PROFILE": ["hcp_name"],
        "GENERATE_SUMMARY": ["hcp_name"],
        "GENERATE_EMAIL": ["hcp_name"],
        "ASSIGN_TAG": ["hcp_name", "tag_name"],
        "CANCEL_APPOINTMENT": ["appointment_id"],
    }

    if action not in required:
        return True, ""

    missing = [p for p in required[action] if not params.get(p)]
    if missing:
        return False, f"Missing required parameters: {', '.join(missing)}"
    return True, ""


# ---------------------------------------------------------------------------
# Pre-LLM input guard
# ---------------------------------------------------------------------------
_MEDICAL_TERMS_RE = re.compile(
    r'\b(headache|fever|pain|cancer|diabetes|hypertension|arthritis|asthma|'
    r'infection|virus|bacteria|syndrome|disorder|disease|arteritis|stenosis|'
    r'carcinoma|lymphoma|leukemia|hepatitis|tuberculosis|malaria|dengue|covid)\b',
    re.IGNORECASE
)
_TRIVIAL_INPUT_RE = re.compile(r'^[\d\s\W]{1,4}$')


def _pre_guard(user_input: str) -> str | None:
    text = user_input.strip()
    if _TRIVIAL_INPUT_RE.match(text):
        return json.dumps({
            "action": "REJECTED",
            "status": "error",
            "tool_used": "GUARD",
            "confidence": 1.0,
            "reason": "Input too short or trivial",
            "result": {"message": "⚠️ Invalid input. Please enter a valid message."}
        })
    if _MEDICAL_TERMS_RE.search(text) and len(text.split()) <= 4:
        return json.dumps({
            "action": "REJECTED",
            "status": "error",
            "tool_used": "GUARD",
            "confidence": 1.0,
            "reason": "Medical symptom query detected",
            "result": {"message": "⚠️ This looks like a medical term or symptom. "
                                   "I cannot provide medical advice. "
                                   "Please consult a doctor."}
        })
    return None


# ---------------------------------------------------------------------------
# Intent Classifier (Router) with Confidence
# ---------------------------------------------------------------------------
_ROUTER_PROMPT = """You are a CRM intent classifier. Classify the user query into ONE intent.
Output ONLY valid JSON. No explanation, no markdown.

Schema: {
  "intent": "INTENT_NAME",
  "confidence": 0.0-1.0,
  "entities": {"doctor": "string or null", "date": "string or null", "time": "string or null", "product": "string or null", "notes": "string or null", "appointment_id": "number or null"}
}

Intents:
- BOOK_APPOINTMENT — user wants to schedule a meeting/appointment with a doctor. Examples: "book Dr. Sharma", "schedule meeting with Dr. Patel on Monday", "appointment with Dr. Kumar at 3pm"
- LOG_INTERACTION — user describes a meeting, call, or visit. Examples: "met Dr. Sharma", "called Dr. Patel", "discussed Lipitor with Dr. Kumar"
- GET_HCP_HISTORY — user asks about past interactions. Examples: "history of Dr. Sharma", "what did I discuss with Dr. Patel", "his interactions"
- GET_HCP_PROFILE — user asks about a doctor's details. Examples: "profile of Dr. Sharma", "who is Dr. Patel"
- LIST_HCPS — list all doctors. Example: "list doctors", "show all HCPs"
- RECOMMEND_HCPS — ask who to visit. Examples: "who should I visit", "recommend HCPs", "priority list"
- GET_INACTIVE_HCPS — find doctors not visited recently. Examples: "inactive doctors", "who haven't I seen"
- GET_FOLLOWUPS — pending follow-ups. Examples: "follow-ups", "who needs follow-up"
- GET_DAILY_SUMMARY — today's report. Examples: "today summary", "daily report"
- FILTER_BY_PRIORITY — filter by priority. Examples: "high priority HCPs", "show medium priority"
- CREATE_TAG — create a tag. Examples: "create tag cholesterol", "new tag"
- ASSIGN_TAG — tag a doctor. Examples: "tag Dr. Sharma as early-adopter"
- GET_HCP_TAGS — get tags for a doctor. Examples: "tags for Dr. Sharma"
- SEARCH_BY_TAG — find doctors by tag. Examples: "doctors tagged influencer"
- SEARCH_NOTES — semantic search. Examples: "doctors discussing cholesterol drugs", "find notes about diabetes"
- GENERATE_SUMMARY — summarize interactions. Examples: "summarize Dr. Sharma's visits", "summary of last 5 interactions"
- GENERATE_EMAIL — draft follow-up email. Examples: "email Dr. Sharma", "draft follow-up email"
- LIST_APPOINTMENTS — show appointments. Examples: "my appointments", "upcoming visits"
- CANCEL_APPOINTMENT — cancel a booking. Examples: "cancel appointment 5", "cancel booking"
- NONE — unclear or missing information

Critical rules:
- Extract doctor names precisely (e.g., "Dr. Sharma" → "Dr. Sharma")
- Extract dates (e.g., "Monday", "2024-12-25", "tomorrow")
- Extract times (e.g., "3pm", "14:30")
- Extract appointment IDs as numbers (e.g., "cancel appointment 5" → appointment_id: 5)
- If the user refers to "he/she/they/his/her" and a doctor was mentioned earlier, classify normally and let downstream resolve it.
- Confidence should be high (0.85-1.0) for clear queries, low (0.5-0.7) for ambiguous ones.

User: USERINPUT"""


async def _classify_intent(user_input: str, session: dict) -> dict:
    """Use LLM to classify intent, extract entities, and score confidence."""
    prompt = _ROUTER_PROMPT.replace("USERINPUT", user_input[:1000])
    try:
        async with asyncio.timeout(_ROUTER_TIMEOUT):
            resp = await get_client().chat(
                model=AGENT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
        result = _extract_json(resp["message"]["content"])
        intent = result.get("intent", "NONE").upper()
        entities = result.get("entities", {})
        confidence = float(result.get("confidence", 0.8))
        # Clamp confidence
        confidence = max(0.0, min(1.0, confidence))
        logger.info(f"Classified intent: {intent} (confidence={confidence}), entities: {entities}")
        return {"intent": intent, "entities": entities, "confidence": confidence}
    except Exception as e:
        logger.error(f"Intent classification error: {e}")
        return {"intent": "NONE", "entities": {}, "confidence": 0.0}


# ---------------------------------------------------------------------------
# Node Handlers
# Each returns a list of JSON strings to yield.
# ---------------------------------------------------------------------------

async def _node_appointment(session: dict, user_input: str) -> list[str]:
    """Multi-step appointment booking:
    identify_intent → extract_doctor → extract_date → extract_time → check_availability → confirm → book
    """
    step = session.get("step", "extract_doctor")
    doctor = session.get("doctor")
    date = session.get("date")
    time = session.get("time")

    # Try to extract from current input if missing
    if not doctor:
        m = re.search(r'(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input)
        if m:
            doctor = m.group(0)
            session["doctor"] = doctor

    if not date:
        m = re.search(r'(\d{4}-\d{2}-\d{2}|tomorrow|today|next\s+\w+|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', user_input, re.IGNORECASE)
        if m:
            date_str = m.group(1).lower()
            if date_str == "today":
                date = datetime.now().strftime("%Y-%m-%d")
            elif date_str == "tomorrow":
                date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                date = date_str
            session["date"] = date

    if not time:
        m = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM)?|\d{1,2}\s*(?:AM|PM))', user_input, re.IGNORECASE)
        if m:
            time = m.group(1)
            session["time"] = time

    # Transition logic
    if not doctor:
        session["step"] = "extract_doctor"
        return [_ask("BOOK_APPOINTMENT", "📅 Which doctor would you like to book an appointment with?")]

    if not date:
        session["step"] = "extract_date"
        return [_ask("BOOK_APPOINTMENT", f"📅 What date would you like to meet with {doctor}? (e.g., 2024-12-25 or tomorrow)")]

    if not time:
        session["step"] = "extract_time"
        return [_ask("BOOK_APPOINTMENT", f"⏰ What time on {date}? (e.g., 14:30 or 3pm)")]

    # Standardize time format
    time_std = _standardize_time(time)
    if not time_std:
        return [_ask("BOOK_APPOINTMENT", "⏰ Please provide a valid time (e.g., 14:30 or 3pm).")]

    # Validate before execution
    valid, err = _validate_tool_params("BOOK_APPOINTMENT", {"doctor": doctor, "date": date, "time": time_std})
    if not valid:
        return [_err("BOOK_APPOINTMENT", err)]

    hcp = await asyncio.to_thread(get_hcp_profile, doctor)
    if not hcp:
        hcp_id = await asyncio.to_thread(upsert_hcp, {"name": doctor})
        hcp = {"id": hcp_id}

    available = await asyncio.to_thread(is_available, hcp["id"], date, time_std)
    if not available:
        alts = await asyncio.to_thread(suggest_alternatives, hcp["id"], date, time_std)
        alt_text = ", ".join(alts) if alts else "none available"
        return [_err("BOOK_APPOINTMENT",
            f"❌ {doctor} is not available at {time_std} on {date}.\n"
            f"Suggested alternatives: {alt_text}",
            reason="Time slot conflict")]

    # Book it
    try:
        appt_id = await asyncio.to_thread(create_appointment, hcp["id"], date, time_std)
        session["step"] = "done"
        session["intent"] = None  # Reset after completion
        return [_ok("BOOK_APPOINTMENT",
            {"doctor": doctor, "date": date, "time": time_std},
            {"appointment_id": appt_id, "status": "booked"},
            reason=f"Booked appointment with {doctor} on {date} at {time_std}")]
    except Exception as e:
        logger.error(f"Booking failed: {e}")
        return [_err("BOOK_APPOINTMENT", "Booking failed due to a system error. Please try again.")]


def _standardize_time(time_str: str) -> str | None:
    """Convert various time formats to HH:MM."""
    time_str = time_str.strip().upper().replace(" ", "")
    # HH:MM AM/PM
    m = re.match(r'(\d{1,2}):(\d{2})(AM|PM)?', time_str)
    if m:
        h, min_val, ampm = int(m.group(1)), m.group(2), m.group(3)
        if ampm == "PM" and h != 12:
            h += 12
        if ampm == "AM" and h == 12:
            h = 0
        return f"{h:02d}:{min_val}"
    return None


async def _node_interaction(session: dict, user_input: str) -> list[str]:
    """Log interaction with auto-extraction."""
    # Try to extract doctor name
    doctor = session.get("doctor")
    if not doctor:
        m = re.search(r'(?:met|called|visited|with)\s+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
        if m:
            doctor = m.group(1)
            session["doctor"] = doctor

    if not doctor:
        return [_ask("LOG_INTERACTION", "👤 Which doctor did you interact with?")]

    notes = user_input
    # Extract entities via LLM
    entities = await extract_entities_from_notes(notes)

    sentiment = entities.get("sentiment", "neutral")
    product = entities.get("drug_mentioned")
    follow_up_date = entities.get("follow_up_date")

    iid = await asyncio.to_thread(
        insert_interaction,
        doctor, notes,
        "call", None, None,
        notes, None, entities,
        sentiment, product, None,
        bool(follow_up_date), follow_up_date,
    )

    # Index in vector store
    try:
        vs = get_vector_store()
        vs.upsert([{
            "id": f"interaction_{iid}",
            "text": f"{doctor}: {notes}",
            "metadata": {"hcp_name": doctor, "interaction_id": iid, "date": datetime.utcnow().isoformat(), "sentiment": sentiment},
        }])
    except Exception as e:
        logger.warning(f"Vector store indexing failed: {e}")

    session["intent"] = None
    session["step"] = "done"
    return [_ok("LOG_INTERACTION",
        {"hcp_name": doctor, "notes": notes},
        {"interaction_id": iid, "entities": entities},
        reason=f"Logged interaction with {doctor}")]


async def _node_recommendation(session: dict, user_input: str) -> list[str]:
    limit = 5
    m = re.search(r'(\d+)', user_input)
    if m:
        limit = min(int(m.group(1)), 20)
    hcps = await asyncio.to_thread(recommend_hcps, limit)
    return [_ok("RECOMMEND_HCPS",
        {"limit": limit},
        {"recommendations": hcps},
        reason=f"Recommended top {len(hcps)} HCPs based on AI scoring")]


async def _node_followups(session: dict, user_input: str) -> list[str]:
    followups = await asyncio.to_thread(get_pending_followups)
    return [_ok("GET_FOLLOWUPS", {},
        {"followups": followups},
        reason=f"Found {len(followups)} pending follow-ups")]


async def _node_summary(session: dict, user_input: str) -> list[str]:
    summary = await asyncio.to_thread(get_daily_summary)
    return [_ok("GET_DAILY_SUMMARY", {},
        {"summary": summary},
        reason="Generated daily activity summary")]


async def _node_search_notes(session: dict, user_input: str) -> list[str]:
    # Extract search query
    query = re.sub(r'^(find|search|show me|doctors discussing|notes about)\s+', '', user_input, flags=re.IGNORECASE).strip()
    vs = get_vector_store()
    results = vs.query(query, top_k=5)
    return [_ok("SEARCH_NOTES",
        {"query": query},
        {"results": results},
        reason=f"Semantic search for '{query}' returned {len(results)} results")]


async def _node_generate_summary(session: dict, user_input: str) -> list[str]:
    doctor = session.get("doctor")
    if not doctor:
        m = re.search(r'(?:summarize|summary of)\s+(?:last \d+\s+interactions of\s+)?(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
        if m:
            doctor = m.group(1)
            session["doctor"] = doctor

    if not doctor:
        return [_ask("GENERATE_SUMMARY", "👤 Which doctor's interactions should I summarize?")]

    # Validate
    valid, err = _validate_tool_params("GENERATE_SUMMARY", {"hcp_name": doctor})
    if not valid:
        return [_err("GENERATE_SUMMARY", err)]

    history = await asyncio.to_thread(get_interactions_by_hcp, doctor)
    ai_sum = await generate_ai_summary(doctor, history)
    session["intent"] = None
    return [_ok("GENERATE_SUMMARY",
        {"hcp_name": doctor},
        {"summary": ai_sum, "interaction_count": len(history)},
        reason=f"Summarized {len(history)} interactions for {doctor}")]


async def _node_generate_email(session: dict, user_input: str) -> list[str]:
    doctor = session.get("doctor")
    if not doctor:
        m = re.search(r'(?:email|draft)\s+(?:follow.up\s+)?(?:to\s+)?(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
        if m:
            doctor = m.group(1)
            session["doctor"] = doctor

    if not doctor:
        return [_ask("GENERATE_EMAIL", "👤 Which doctor should I draft a follow-up email for?")]

    valid, err = _validate_tool_params("GENERATE_EMAIL", {"hcp_name": doctor})
    if not valid:
        return [_err("GENERATE_EMAIL", err)]

    history = await asyncio.to_thread(get_interactions_by_hcp, doctor)
    if not history:
        return [_err("GENERATE_EMAIL", f"No interactions found for {doctor}.")]

    email = await generate_followup_email(doctor, history[0])
    session["intent"] = None
    return [_ok("GENERATE_EMAIL",
        {"hcp_name": doctor},
        {"email": email},
        reason=f"Generated follow-up email for {doctor}")]


async def _node_list_appointments(session: dict, user_input: str) -> list[str]:
    appts = await asyncio.to_thread(get_appointments)
    return [_ok("LIST_APPOINTMENTS", {},
        {"appointments": appts},
        reason=f"Listed {len(appts)} appointments")]


async def _node_cancel_appointment(session: dict, user_input: str) -> list[str]:
    """
    Cancel an appointment by ID.
    Multi-step: if no appointment_id in session, ask for it.
    If appointment_id is provided (from user input or session), cancel it.
    """
    # Try to extract appointment_id from input
    appointment_id = session.get("appointment_id")
    if not appointment_id:
        m = re.search(r'(\d+)', user_input)
        if m:
            appointment_id = int(m.group(1))
            session["appointment_id"] = appointment_id

    if not appointment_id:
        session["step"] = "extract_appointment_id"
        return [_ask("CANCEL_APPOINTMENT",
            "Please provide the appointment ID to cancel. You can find it by saying 'list appointments'.")]

    # Validate
    valid, err = _validate_tool_params("CANCEL_APPOINTMENT", {"appointment_id": appointment_id})
    if not valid:
        return [_err("CANCEL_APPOINTMENT", err)]

    # Verify appointment exists
    appt = await asyncio.to_thread(get_appointment_by_id, appointment_id)
    if not appt:
        return [_err("CANCEL_APPOINTMENT", f"Appointment {appointment_id} not found.")]

    # Cancel
    cancelled = await asyncio.to_thread(cancel_appointment, appointment_id)
    if cancelled:
        session["appointment_id"] = None
        session["step"] = "done"
        session["intent"] = None
        return [_ok("CANCEL_APPOINTMENT",
            {"appointment_id": appointment_id},
            {"status": "cancelled", "appointment": appt},
            reason=f"Cancelled appointment {appointment_id} with {appt['hcp_name']}")]

    return [_err("CANCEL_APPOINTMENT", f"Could not cancel appointment {appointment_id}.")]


async def _node_get_hcp_history(session: dict, user_input: str) -> list[str]:
    doctor = session.get("doctor")
    if not doctor:
        m = re.search(r'(?:history of|interactions with)\s+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
        if m:
            doctor = m.group(1)
            session["doctor"] = doctor
    if not doctor:
        return [_ask("GET_HCP_HISTORY", "👤 Which doctor's history would you like to see?")]
    history = await asyncio.to_thread(get_interactions_by_hcp, doctor)
    return [_ok("GET_HCP_HISTORY",
        {"hcp_name": doctor},
        {"history": history},
        reason=f"Retrieved {len(history)} interactions for {doctor}")]


async def _node_get_hcp_profile(session: dict, user_input: str) -> list[str]:
    doctor = session.get("doctor")
    if not doctor:
        m = re.search(r'(?:profile of|who is)\s+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
        if m:
            doctor = m.group(1)
            session["doctor"] = doctor
    if not doctor:
        return [_ask("GET_HCP_PROFILE", "👤 Which doctor's profile would you like to see?")]
    profile = await asyncio.to_thread(get_hcp_profile, doctor)
    if not profile:
        return [_err("GET_HCP_PROFILE", f"No HCP found with name '{doctor}'.")]
    return [_ok("GET_HCP_PROFILE",
        {"hcp_name": doctor},
        {"profile": profile},
        reason=f"Retrieved profile for {doctor}")]


async def _node_list_hcps(session: dict, user_input: str) -> list[str]:
    hcps = await asyncio.to_thread(get_all_hcp)
    return [_ok("LIST_HCPS", {},
        {"hcps": hcps},
        reason=f"Listed {len(hcps)} HCPs")]


async def _node_get_inactive_hcps(session: dict, user_input: str) -> list[str]:
    m = re.search(r'(\d+)', user_input)
    days = int(m.group(1)) if m else 30
    hcps = await asyncio.to_thread(get_inactive_hcps, days)
    return [_ok("GET_INACTIVE_HCPS",
        {"days": days},
        {"inactive_hcps": hcps},
        reason=f"Found {len(hcps)} inactive HCPs (> {days} days)")]


async def _node_filter_by_priority(session: dict, user_input: str) -> list[str]:
    m = re.search(r'(high|medium|low)', user_input, re.IGNORECASE)
    priority = m.group(1).lower() if m else "high"
    hcps = await asyncio.to_thread(get_hcps_by_priority, priority)
    return [_ok("FILTER_BY_PRIORITY",
        {"priority": priority},
        {"hcps": hcps},
        reason=f"Found {len(hcps)} {priority} priority HCPs")]


async def _node_create_tag(session: dict, user_input: str) -> list[str]:
    m = re.search(r'(?:create tag|new tag|tag name)\s+([\w\s-]+)', user_input, re.IGNORECASE)
    if not m:
        return [_ask("CREATE_TAG", "🏷️ What should the tag be called?")]
    tag_name = m.group(1).strip()
    tag_id = await asyncio.to_thread(upsert_tag, tag_name)
    return [_ok("CREATE_TAG",
        {"name": tag_name},
        {"tag_id": tag_id},
        reason=f"Created tag '{tag_name}'")]


async def _node_assign_tag(session: dict, user_input: str) -> list[str]:
    doctor = session.get("doctor")
    if not doctor:
        m = re.search(r'(?:tag|assign)\s+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
        if m:
            doctor = m.group(1)
            session["doctor"] = doctor
    if not doctor:
        return [_ask("ASSIGN_TAG", "👤 Which doctor should I tag?")]
    m = re.search(r'(?:as|with|tag)\s+([\w\s-]+)$', user_input, re.IGNORECASE)
    tag_name = m.group(1).strip() if m else None
    if not tag_name:
        return [_ask("ASSIGN_TAG", "🏷️ Which tag should I assign?")]

    hcp = await asyncio.to_thread(get_hcp_profile, doctor)
    if not hcp:
        return [_err("ASSIGN_TAG", f"No HCP found with name '{doctor}'.")]
    tag = await asyncio.to_thread(get_tag_by_name, tag_name)
    tag_id = tag["id"] if tag else await asyncio.to_thread(upsert_tag, tag_name, "auto", None)
    assigned = await asyncio.to_thread(assign_tag_to_hcp, hcp["id"], tag_id, None, "llm")
    if not assigned:
        return [_err("ASSIGN_TAG", f"Tag '{tag_name}' is already assigned to '{doctor}'.")]
    return [_ok("ASSIGN_TAG",
        {"hcp_name": doctor, "tag_name": tag_name},
        {"assigned": True},
        reason=f"Assigned tag '{tag_name}' to {doctor}")]


async def _node_get_hcp_tags(session: dict, user_input: str) -> list[str]:
    doctor = session.get("doctor")
    if not doctor:
        m = re.search(r'(?:tags for|tags of)\s+(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)', user_input, re.IGNORECASE)
        if m:
            doctor = m.group(1)
            session["doctor"] = doctor
    if not doctor:
        return [_ask("GET_HCP_TAGS", "👤 Which doctor's tags would you like to see?")]
    tags = await asyncio.to_thread(get_hcp_tags, doctor)
    return [_ok("GET_HCP_TAGS",
        {"hcp_name": doctor},
        {"tags": tags},
        reason=f"Retrieved {len(tags)} tags for {doctor}")]


async def _node_search_by_tag(session: dict, user_input: str) -> list[str]:
    m = re.search(r'(?:tagged|with tag)\s+([\w\s-]+)', user_input, re.IGNORECASE)
    tag_name = m.group(1).strip() if m else None
    if not tag_name:
        return [_ask("SEARCH_BY_TAG", "🏷️ Which tag should I search for?")]
    hcps = await asyncio.to_thread(get_hcps_by_tag, tag_name)
    return [_ok("SEARCH_BY_TAG",
        {"tag_name": tag_name},
        {"hcps": hcps},
        reason=f"Found {len(hcps)} HCPs tagged '{tag_name}'")]


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------
_NODE_DISPATCH = {
    "BOOK_APPOINTMENT":    _node_appointment,
    "LOG_INTERACTION":     _node_interaction,
    "GET_HCP_HISTORY":     _node_get_hcp_history,
    "GET_HCP_PROFILE":     _node_get_hcp_profile,
    "LIST_HCPS":           _node_list_hcps,
    "RECOMMEND_HCPS":      _node_recommendation,
    "GET_INACTIVE_HCPS":   _node_get_inactive_hcps,
    "GET_FOLLOWUPS":       _node_followups,
    "GET_DAILY_SUMMARY":   _node_summary,
    "FILTER_BY_PRIORITY":  _node_filter_by_priority,
    "CREATE_TAG":          _node_create_tag,
    "ASSIGN_TAG":          _node_assign_tag,
    "GET_HCP_TAGS":        _node_get_hcp_tags,
    "SEARCH_BY_TAG":       _node_search_by_tag,
    "SEARCH_NOTES":        _node_search_notes,
    "GENERATE_SUMMARY":    _node_generate_summary,
    "GENERATE_EMAIL":      _node_generate_email,
    "LIST_APPOINTMENTS":   _node_list_appointments,
    "CANCEL_APPOINTMENT":  _node_cancel_appointment,
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def run_agent_stream(user_input: str, session_id: str = "default"):
    """Main agent entry point with session memory, anaphora resolution, and confidence."""
    logger.info(f"Agent invoked [session={session_id}]: {user_input[:200]}")
    _cleanup_sessions()
    session = _get_session(session_id)

    # Resolve anaphora before processing
    resolved_input = _resolve_anaphora(user_input, session)
    session["history"].append({"role": "user", "content": resolved_input, "time": datetime.utcnow().isoformat()})

    try:
        # Pre-LLM guard
        if rejection := _pre_guard(resolved_input):
            yield rejection
            return

        # If we're in the middle of a multi-step flow, keep the intent
        current_intent = session.get("intent")
        if current_intent and current_intent in _NODE_DISPATCH and session.get("step") != "done":
            intent = current_intent
            entities = {}
            confidence = 1.0
        else:
            # Classify intent with confidence
            classification = await _classify_intent(resolved_input, session)
            intent = classification["intent"]
            entities = classification["entities"]
            confidence = classification["confidence"]
            # Seed session with extracted entities
            if entities.get("doctor"):
                session["doctor"] = entities["doctor"]
            if entities.get("date"):
                session["date"] = entities["date"]
            if entities.get("time"):
                session["time"] = entities["time"]
            if entities.get("appointment_id"):
                session["appointment_id"] = int(entities["appointment_id"])

            # Low confidence fallback
            if confidence < 0.6 and intent != "NONE":
                logger.warning(f"Low confidence ({confidence
