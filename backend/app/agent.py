import re
import json
import logging
import asyncio
from datetime import datetime, timedelta
from .config import AGENT_MODEL, AGENT_TIMEOUT
from .llm_client import chat_json, chat_stream, get_client
from .ai_tools import build_llm_tool_prompt
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
    create_appointment,
    is_available,
    get_appointments,
    suggest_alternatives,
    get_appointment_by_id,
    cancel_appointment,
)

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r'```json\s*(.*?)\s*```', re.DOTALL)
_ROUTER_TIMEOUT = max(10, AGENT_TIMEOUT // 2)

ACTION_CREATE_HCP         = "CREATE_HCP"
ACTION_LOG_INTERACTION    = "LOG_INTERACTION"
ACTION_GET_HCP_HISTORY    = "GET_HCP_HISTORY"
ACTION_GET_HCP_PROFILE    = "GET_HCP_PROFILE"
ACTION_LIST_HCPS          = "LIST_HCPS"
ACTION_RECOMMEND_HCPS     = "RECOMMEND_HCPS"
ACTION_GET_INACTIVE_HCPS  = "GET_INACTIVE_HCPS"
ACTION_FILTER_BY_PRIORITY = "FILTER_BY_PRIORITY"
ACTION_GET_FOLLOWUPS      = "GET_FOLLOWUPS"
ACTION_GET_DAILY_SUMMARY  = "GET_DAILY_SUMMARY"
ACTION_CREATE_TAG         = "CREATE_TAG"
ACTION_ASSIGN_TAG         = "ASSIGN_TAG"
ACTION_GET_HCP_TAGS       = "GET_HCP_TAGS"
ACTION_SEARCH_BY_TAG      = "SEARCH_BY_TAG"
ACTION_BOOK_APPOINTMENT   = "BOOK_APPOINTMENT"
ACTION_LIST_APPOINTMENTS  = "LIST_APPOINTMENTS"
ACTION_CANCEL_APPOINTMENT = "CANCEL_APPOINTMENT"
ACTION_SEARCH_NOTES       = "SEARCH_NOTES"
ACTION_GENERATE_SUMMARY   = "GENERATE_SUMMARY"
ACTION_GENERATE_EMAIL     = "GENERATE_EMAIL"
ACTION_NONE               = "NONE"

_SESSIONS: dict[str, dict] = {}
_MAX_SESSIONS = 1000  # Cap to prevent unbounded memory growth


def _get_session(session_id: str) -> dict:
    if session_id not in _SESSIONS:
        # Evict oldest sessions if at capacity
        if len(_SESSIONS) >= _MAX_SESSIONS:
            oldest = next(iter(_SESSIONS))
            _SESSIONS.pop(oldest)
        _SESSIONS[session_id] = {
            "history": [],
            "context": {},
            "pending_action": None,
            "pending_params": {},
        }
    return _SESSIONS[session_id]


def _clear_session(session_id: str) -> None:
    _SESSIONS.pop(session_id, None)


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


def _ok(action: str, params: dict, result: dict, tool_used: str = "", reason: str = "", confidence: float = 1.0) -> str:
    return json.dumps({
        "action": action,
        "status": "ok",
        "params": params,
        "result": result,
        "tool_used": tool_used or action,
        "reason": reason,
        "confidence": confidence,
    }, default=str)


def _err(action: str, message: str, tool_used: str = "", reason: str = "", confidence: float = 0.0) -> str:
    return json.dumps({
        "action": action,
        "status": "error",
        "result": {"message": message},
        "tool_used": tool_used or action,
        "reason": reason,
        "confidence": confidence,
    })


def _ask(action: str, message: str) -> str:
    return json.dumps({
        "action": action,
        "status": "ask",
        "result": {"message": message},
    })


def _require(params: dict, *keys: str) -> str | None:
    for k in keys:
        if not str(params.get(k, "")).strip():
            return k
    return None


_MEDICAL_TERMS_RE = re.compile(
    r'\b(headache|fever|pain|cancer|diabetes|hypertension|arthritis|asthma|'
    r'infection|virus|bacteria|syndrome|disorder|disease|arteritis|stenosis|'
    r'carcinoma|lymphoma|leukemia|hepatitis|tuberculosis|malaria|dengue|covid)\b',
    re.IGNORECASE
)
_TRIVIAL_INPUT_RE = re.compile(r'^[\d\s\W]{1,4}$')


def _pre_guard(user_input: str) -> str | None:
    text = user_input.strip()
    if not text or _TRIVIAL_INPUT_RE.match(text):
        return json.dumps({"action": "REJECTED", "status": "error",
                           "result": {"message": "⚠️ Invalid input. Please enter a valid message."}})
    if _MEDICAL_TERMS_RE.search(text) and len(text.split()) <= 4:
        return json.dumps({"action": "REJECTED", "status": "error",
                           "result": {"message": "⚠️ This looks like a medical term or symptom. "
                                                  "I cannot provide medical advice. "
                                                  "Please consult a doctor."}})
    return None


def _validate_hcp_name(name: str) -> str | None:
    name = name.strip()
    if len(name) < 3:
        return "HCP name must be at least 3 characters."
    if re.fullmatch(r'[\d\s\W]+', name):
        return "HCP name must contain letters."
    if _MEDICAL_TERMS_RE.fullmatch(name.lower()):
        return f"'{name}' appears to be a medical term, not a person's name."
    return None


def _rule_classify(user_input: str) -> dict | None:
    """Fast rule-based intent classification. Returns None if no match."""
    text = user_input.strip().lower()

    doctor_match = re.search(r"\b(dr\.?\s+[a-zA-Z]+)", user_input.strip(), re.IGNORECASE)
    doctor = doctor_match.group(0).strip() if doctor_match else None

    # Generate email - check BEFORE follow-ups to avoid "draft follow-up email" matching follow-ups
    if "email" in text and ("draft" in text or "follow-up" in text or "generate" in text):
        return {"intent": ACTION_GENERATE_EMAIL, "entities": {"doctor": doctor} if doctor else {}, "confidence": 0.85}

    # Follow-ups
    if any(k in text for k in ("follow-up", "follow up", "who needs follow")):
        return {"intent": ACTION_GET_FOLLOWUPS, "entities": {}, "confidence": 0.9}

    # Priority filter
    if "priority" in text:
        p_match = re.search(r"\b(high|medium|low)\b", text)
        if p_match:
            return {"intent": ACTION_FILTER_BY_PRIORITY, "entities": {"priority": p_match.group(1)}, "confidence": 0.9}

    # Log interaction
    if any(k in text for k in ("met", "called", "visited", "discussed", "log ", "talked to")):
        return {"intent": ACTION_LOG_INTERACTION, "entities": {"doctor": doctor} if doctor else {}, "confidence": 0.85}

    # Recommend
    if any(k in text for k in ("recommend", "who should i visit", "what should i do next")):
        return {"intent": ACTION_RECOMMEND_HCPS, "entities": {}, "confidence": 0.9}

    # List doctors
    if any(k in text for k in ("list all doctors", "all doctors", "list hcps")):
        return {"intent": ACTION_LIST_HCPS, "entities": {}, "confidence": 0.9}

    # Daily summary - check BEFORE generic "show/summary" to catch "show today summary"
    if any(k in text for k in ("today summary", "daily report", "performance")):
        return {"intent": ACTION_GET_DAILY_SUMMARY, "entities": {}, "confidence": 0.9}

    # Show / profile / history
    if any(k in text for k in ("show", "profile", "history", "summarize", "summary")):
        if "last" in text and "interactions" in text:
            return {"intent": ACTION_GENERATE_SUMMARY, "entities": {"doctor": doctor} if doctor else {}, "confidence": 0.85}
        if "history" in text:
            return {"intent": ACTION_GET_HCP_HISTORY, "entities": {"doctor": doctor} if doctor else {}, "confidence": 0.85}
        if "summary" in text or "summarize" in text:
            return {"intent": ACTION_GENERATE_SUMMARY, "entities": {"doctor": doctor} if doctor else {}, "confidence": 0.85}
        if doctor:
            return {"intent": ACTION_GET_HCP_PROFILE, "entities": {"doctor": doctor}, "confidence": 0.85}

    # Book appointment
    if any(k in text for k in ("book", "schedule", "reserve")):
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|tomorrow|today)\b", text)
        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", text)
        entities = {}
        if doctor:
            entities["doctor"] = doctor
        if date_match:
            entities["date"] = date_match.group(1)
        if time_match:
            entities["time"] = time_match.group(1)
        return {"intent": ACTION_BOOK_APPOINTMENT, "entities": entities, "confidence": 0.9}

    # Cancel appointment
    if "cancel" in text and ("appointment" in text or re.search(r"\b\d+\b", text)):
        appt_match = re.search(r"\b(\d+)\b", text)
        entities = {"appointment_id": int(appt_match.group(1))} if appt_match else {}
        return {"intent": ACTION_CANCEL_APPOINTMENT, "entities": entities, "confidence": 0.9}

    # List appointments
    if "my appointments" in text or ("list" in text and "appointment" in text):
        return {"intent": ACTION_LIST_APPOINTMENTS, "entities": {}, "confidence": 0.9}

    # Tag operations
    if "tag" in text or "tagged" in text:
        if "create" in text:
            name_match = re.search(r"tag\s+(\S+)", text)
            return {"intent": ACTION_CREATE_TAG, "entities": {"name": name_match.group(1)} if name_match else {}, "confidence": 0.85}
        if "search" in text or "doctors tagged" in text:
            tag_match = re.search(r"tagged\s+(\S+)", text)
            return {"intent": ACTION_SEARCH_BY_TAG, "entities": {"tag_name": tag_match.group(1)} if tag_match else {}, "confidence": 0.85}
        if doctor:
            tag_match = re.search(r"as\s+(\S+)", text)
            return {"intent": ACTION_ASSIGN_TAG, "entities": {"doctor": doctor, "tag": tag_match.group(1) if tag_match else "auto"}, "confidence": 0.85}

    # Inactive
    if "inactive" in text:
        d_match = re.search(r"(\d+)\s+days", text)
        return {"intent": ACTION_GET_INACTIVE_HCPS, "entities": {"days": int(d_match.group(1))} if d_match else {}, "confidence": 0.85}

    # Search notes
    if "search notes" in text or "notes about" in text:
        q_match = re.search(r"about\s+(.+)", text)
        return {"intent": ACTION_SEARCH_NOTES, "entities": {"query": q_match.group(1)} if q_match else {}, "confidence": 0.85}

    return None


async def _classify_intent(user_input: str, session: dict) -> dict:
    """Hybrid intent classification: fast rules first, then LLM JSON fallback."""
    resolved_input = _resolve_anaphora(user_input, session)
    rule_result = _rule_classify(resolved_input)
    if rule_result:
        logger.info(f"Rule-based intent: {rule_result['intent']} for '{resolved_input[:100]}'")
        return rule_result

    # LLM fallback for paraphrased / novel queries
    try:
        llm_resp = await chat_json(
            messages=[
                {"role": "system", "content": build_llm_tool_prompt()},
                {"role": "user", "content": f"Classify this query: '{resolved_input[:500]}'"},
            ],
            timeout=_ROUTER_TIMEOUT,
        )
        intent = llm_resp.get("intent", "NONE")
        if intent in _NODE_DISPATCH or intent == "NONE":
            logger.info(f"LLM intent: {intent} for '{resolved_input[:100]}'")
            return {
                "intent": intent,
                "entities": llm_resp.get("entities", {}),
                "confidence": float(llm_resp.get("confidence", 0.7)),
            }
    except Exception as e:
        logger.warning(f"LLM classification failed: {e}")

    logger.info(f"No match for '{resolved_input[:100]}', returning NONE")
    return {"intent": "NONE", "entities": {}, "confidence": 0.0}


def _resolve_anaphora(user_input: str, session: dict) -> str:
    """Replace pronouns with last mentioned HCP name from context."""
    text = user_input.strip().lower()
    pronouns = ("his", "her", "their", "they", "them", "he", "she", "him")
    # Check for pronouns with word boundaries (handles punctuation like "What's his...")
    if not any(re.search(rf'\b{p}\b', text) for p in pronouns):
        return user_input
    last_doctor = session.get("context", {}).get("last_doctor")
    if not last_doctor:
        return user_input
    resolved = user_input
    for pronoun in pronouns:
        resolved = re.sub(rf'\b{pronoun}\b', last_doctor, resolved, flags=re.IGNORECASE)
    return resolved


async def _handle_create_hcp(params: dict, **kwargs):
    if missing := _require(params, "name"):
        yield _err(ACTION_CREATE_HCP,
            "Please provide the doctor's name. Example: 'Add Dr. Sharma, cardiologist at Apollo Hospital'")
        return
    if err := _validate_hcp_name(params["name"]):
        yield _err(ACTION_CREATE_HCP, err)
        return
    hcp_id = await asyncio.to_thread(upsert_hcp, params)
    yield _ok(ACTION_CREATE_HCP, params, {"hcp_id": hcp_id}, tool_used="upsert_hcp")


async def _handle_log_interaction(params: dict, **kwargs):
    if missing := _require(params, "hcp_name", "notes"):
        if missing == "hcp_name":
            yield _err(ACTION_LOG_INTERACTION,
                "Please specify which doctor you interacted with. Example: 'Met Dr. Sharma today, discussed Lipitor'")
        else:
            yield _err(ACTION_LOG_INTERACTION,
                "Please describe what happened. Example: 'Discussed new drug trial, positive outcome'")
        return
    hcp_name = params["hcp_name"].strip()
    notes    = params["notes"].strip()
    iid = await asyncio.to_thread(
        insert_interaction,
        hcp_name, notes,
        params.get("interaction_type", "call"),
        params.get("interaction_channel"),
        params.get("interaction_date"),
        params.get("raw_input"),
        params.get("ai_summary"),
        params.get("ai_entities"),
        params.get("sentiment"),
        params.get("product_discussed"),
        params.get("outcome"),
        bool(params.get("follow_up_required", False)),
        params.get("follow_up_date"),
    )
    yield _ok(ACTION_LOG_INTERACTION, {"hcp_name": hcp_name, "notes": notes}, {"interaction_id": iid}, tool_used="insert_interaction")


async def _handle_get_hcp_history(params: dict, **kwargs):
    if missing := _require(params, "hcp_name"):
        yield _err(ACTION_GET_HCP_HISTORY, f"'{missing}' is required.")
        return
    name = params["hcp_name"].strip()
    history = await asyncio.to_thread(get_interactions_by_hcp, name)
    yield _ok(ACTION_GET_HCP_HISTORY, {"hcp_name": name}, {"history": history}, tool_used="get_interactions_by_hcp")


async def _handle_get_hcp_profile(params: dict, **kwargs):
    if missing := _require(params, "hcp_name"):
        yield _err(ACTION_GET_HCP_PROFILE, f"'{missing}' is required.")
        return
    name = params["hcp_name"].strip()
    profile = await asyncio.to_thread(get_hcp_profile, name)
    if not profile:
        yield _err(ACTION_GET_HCP_PROFILE, f"No HCP found with name '{name}'.")
        return
    yield _ok(ACTION_GET_HCP_PROFILE, {"hcp_name": name}, {"profile": profile}, tool_used="get_hcp_profile")


async def _handle_list_hcps(params: dict, **kwargs):
    hcps = await asyncio.to_thread(get_all_hcp)
    yield _ok(ACTION_LIST_HCPS, {}, {"hcps": hcps}, tool_used="get_all_hcp")


async def _handle_recommend_hcps(params: dict, **kwargs):
    limit = int(params.get("limit", 5))
    hcps = await asyncio.to_thread(recommend_hcps, limit)
    yield _ok(ACTION_RECOMMEND_HCPS, {"limit": limit}, {"recommendations": hcps}, tool_used="recommend_hcps")


async def _handle_get_inactive_hcps(params: dict, **kwargs):
    days = int(params.get("days", 30))
    hcps = await asyncio.to_thread(get_inactive_hcps, days)
    yield _ok(ACTION_GET_INACTIVE_HCPS, {"days": days}, {"inactive_hcps": hcps}, tool_used="get_inactive_hcps")


async def _handle_get_followups(params: dict, **kwargs):
    followups = await asyncio.to_thread(get_pending_followups)
    yield _ok(ACTION_GET_FOLLOWUPS, {}, {"followups": followups}, tool_used="get_pending_followups")


async def _handle_get_daily_summary(params: dict, **kwargs):
    summary = await asyncio.to_thread(get_daily_summary)
    yield _ok(ACTION_GET_DAILY_SUMMARY, {}, {"summary": summary}, tool_used="get_daily_summary")


async def _handle_filter_by_priority(params: dict, **kwargs):
    priority = params.get("priority", "").strip().lower()
    if priority not in ("high", "medium", "low"):
        yield _err(ACTION_FILTER_BY_PRIORITY, "Priority must be high, medium, or low.")
        return
    hcps = await asyncio.to_thread(get_hcps_by_priority, priority)
    yield _ok(ACTION_FILTER_BY_PRIORITY, {"priority": priority}, {"hcps": hcps}, tool_used="get_hcps_by_priority")


async def _handle_create_tag(params: dict, **kwargs):
    if missing := _require(params, "name"):
        yield _err(ACTION_CREATE_TAG, f"'{missing}' is required.")
        return
    tag_id = await asyncio.to_thread(
        upsert_tag, params["name"].strip(), params.get("category"), params.get("description")
    )
    yield _ok(ACTION_CREATE_TAG, params, {"tag_id": tag_id}, tool_used="upsert_tag")


async def _handle_assign_tag(params: dict, **kwargs):
    if missing := _require(params, "hcp_name", "tag_name"):
        yield _err(ACTION_ASSIGN_TAG, f"'{missing}' is required.")
        return
    hcp_name = params["hcp_name"].strip()
    tag_name = params["tag_name"].strip()
    hcp = await asyncio.to_thread(get_hcp_profile, hcp_name)
    if not hcp:
        yield _err(ACTION_ASSIGN_TAG, f"No HCP found with name '{hcp_name}'.")
        return
    tag = await asyncio.to_thread(get_tag_by_name, tag_name)
    tag_id = tag["id"] if tag else await asyncio.to_thread(upsert_tag, tag_name, "auto", None)
    confidence = params.get("confidence_score")
    if confidence is not None:
        try:
            confidence = float(confidence)
        except (ValueError, TypeError):
            confidence = None
    assigned = await asyncio.to_thread(assign_tag_to_hcp, hcp["id"], tag_id, confidence, "llm")
    if not assigned:
        yield _err(ACTION_ASSIGN_TAG, f"Tag '{tag_name}' is already assigned to '{hcp_name}'.")
        return
    yield _ok(ACTION_ASSIGN_TAG, {"hcp_name": hcp_name, "tag_name": tag_name}, {"assigned": True}, tool_used="assign_tag_to_hcp")


async def _handle_get_hcp_tags(params: dict, **kwargs):
    if missing := _require(params, "hcp_name"):
        yield _err(ACTION_GET_HCP_TAGS, f"'{missing}' is required.")
        return
    name = params["hcp_name"].strip()
    tags = await asyncio.to_thread(get_hcp_tags, name)
    yield _ok(ACTION_GET_HCP_TAGS, {"hcp_name": name}, {"tags": tags}, tool_used="get_hcp_tags")


async def _handle_search_by_tag(params: dict, **kwargs):
    if missing := _require(params, "tag_name"):
        yield _err(ACTION_SEARCH_BY_TAG, f"'{missing}' is required.")
        return
    tag_name = params["tag_name"].strip()
    hcps = await asyncio.to_thread(get_hcps_by_tag, tag_name)
    yield _ok(ACTION_SEARCH_BY_TAG, {"tag_name": tag_name}, {"hcps": hcps}, tool_used="get_hcps_by_tag")


async def _handle_book_appointment(params: dict, session: dict | None = None, **kwargs):
    sess = session or {}
    pending = sess.get("pending_params", {})
    raw_input = params.get("raw_input", "")
    doctor = params.get("doctor") or params.get("hcp_name") or pending.get("doctor")
    # Try to parse date/time from raw_input if not in params
    date_str = params.get("date") or pending.get("date")
    time_str = params.get("time") or pending.get("time")
    if not date_str:
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|tomorrow|today)\b", raw_input, re.IGNORECASE)
        if date_match:
            date_str = date_match.group(1)
    if not time_str:
        time_match = re.search(r"\b(\d{1,2}:\d{2})\b", raw_input)
        if time_match:
            time_str = time_match.group(1)
    if not doctor:
        sess["pending_action"] = ACTION_BOOK_APPOINTMENT
        sess["pending_params"] = {"date": date_str, "time": time_str}
        yield _ask(ACTION_BOOK_APPOINTMENT, "Which doctor would you like to book an appointment with?")
        return
    if not date_str:
        sess["pending_action"] = ACTION_BOOK_APPOINTMENT
        sess["pending_params"] = {"doctor": doctor, "time": time_str}
        yield _ask(ACTION_BOOK_APPOINTMENT, f"What date would you like to book with {doctor}?")
        return
    if not time_str:
        sess["pending_action"] = ACTION_BOOK_APPOINTMENT
        sess["pending_params"] = {"doctor": doctor, "date": date_str}
        yield _ask(ACTION_BOOK_APPOINTMENT, f"What time would you like to book with {doctor} on {date_str}?")
        return
    resolved_date = _resolve_date(date_str)
    hcp = await asyncio.to_thread(get_hcp_profile, doctor)
    if not hcp:
        sess["pending_action"] = None
        sess["pending_params"] = {}
        yield _err(ACTION_BOOK_APPOINTMENT, f"No HCP found with name '{doctor}'.")
        return
    available = await asyncio.to_thread(is_available, hcp["id"], resolved_date, time_str)
    if not available:
        sess["pending_action"] = None
        sess["pending_params"] = {}
        alternatives = await asyncio.to_thread(suggest_alternatives, hcp["id"], resolved_date, time_str)
        alt_msg = f" That slot is not available. Alternative times: {', '.join(alternatives)}" if alternatives else ""
        yield _err(ACTION_BOOK_APPOINTMENT, f"Dr. {doctor} is not available at {time_str} on {resolved_date}.{alt_msg}")
        return
    appt_id = await asyncio.to_thread(create_appointment, hcp["id"], resolved_date, time_str, params.get("notes"))
    yield _ok(ACTION_BOOK_APPOINTMENT, {"doctor": doctor, "date": resolved_date, "time": time_str},
               {"appointment_id": appt_id, "status": "booked"}, tool_used="create_appointment")
    sess["pending_action"] = None
    sess["pending_params"] = {}


async def _handle_list_appointments(params: dict, **kwargs):
    doctor = params.get("doctor") or params.get("hcp_name")
    date_str = params.get("date")
    status = params.get("status")
    appointments = await asyncio.to_thread(get_appointments, doctor, date_str, status)
    yield _ok(ACTION_LIST_APPOINTMENTS, {}, {"appointments": appointments}, tool_used="get_appointments")


async def _handle_cancel_appointment(params: dict, session: dict | None = None, **kwargs):
    appt_id = params.get("appointment_id")
    if not appt_id:
        match = re.search(r'\b(\d+)\b', str(params.get("raw_input", "")))
        if match:
            appt_id = int(match.group(1))
    if not appt_id:
        yield _ask(ACTION_CANCEL_APPOINTMENT, "Which appointment would you like to cancel? Please provide the appointment ID.")
        return
    cancelled = await asyncio.to_thread(cancel_appointment, int(appt_id))
    if not cancelled:
        yield _err(ACTION_CANCEL_APPOINTMENT, f"Appointment {appt_id} not found or already cancelled.")
        return
    yield _ok(ACTION_CANCEL_APPOINTMENT, {"appointment_id": int(appt_id)}, {"cancelled": True}, tool_used="cancel_appointment")


async def _handle_search_notes(params: dict, **kwargs):
    query = params.get("query", "").strip()
    if not query:
        yield _err(ACTION_SEARCH_NOTES, "Please provide a search query.")
        return
    # Semantic search via TF-IDF vector store
    from .vector_store import search_notes
    results = await asyncio.to_thread(search_notes, query, top_k=10)
    yield _ok(ACTION_SEARCH_NOTES, {"query": query}, {"results": results}, tool_used="semantic_search")


async def _handle_generate_summary(params: dict, **kwargs):
    doctor = params.get("doctor") or params.get("hcp_name")
    if not doctor:
        yield _ask(ACTION_GENERATE_SUMMARY, "Which doctor's interactions would you like me to summarize?")
        return
    history = await asyncio.to_thread(get_interactions_by_hcp, doctor)
    if not history:
        yield _err(ACTION_GENERATE_SUMMARY, f"No interactions found for {doctor}.")
        return
    notes_text = "\n".join(f"[{i+1}] {h.get('interaction_date','')} | {h.get('interaction_type','')} | {h.get('notes','')}" for i, h in enumerate(history[:10]))
    # Try LLM summarization; fallback to concatenation if Ollama is down
    try:
        llm_summary = await chat_json(
            messages=[
                {"role": "system", "content": "Summarize these doctor interaction notes into 3-5 bullet points. Be concise."},
                {"role": "user", "content": notes_text[:2000]},
            ],
            timeout=_ROUTER_TIMEOUT,
        )
        summary = llm_summary.get("summary") or llm_summary.get("content") or llm_summary.get("result", "")
        if not summary:
            raise ValueError("Empty LLM summary")
    except Exception as e:
        logger.warning(f"LLM summary failed, using concatenation fallback: {e}")
        summary = "\n".join(f"- {h['notes']}" for h in history[:5])
    yield _ok(ACTION_GENERATE_SUMMARY, {"hcp_name": doctor},
               {"summary": summary, "interaction_count": len(history)}, tool_used="llm_summary")


async def _handle_generate_email(params: dict, **kwargs):
    doctor = params.get("doctor") or params.get("hcp_name")
    if not doctor:
        yield _ask(ACTION_GENERATE_EMAIL, "Which doctor should I draft a follow-up email for?")
        return
    history = await asyncio.to_thread(get_interactions_by_hcp, doctor)
    if not history:
        yield _err(ACTION_GENERATE_EMAIL, f"No interactions found for {doctor}.")
        return
    latest = history[0]
    product = latest.get("product_discussed", "our product")
    email = f"""Subject: Follow-up on {product}

Dear {doctor},

Thank you for your time during our recent discussion about {product}.
I wanted to follow up on the points we covered and see if you have any further questions.

Best regards,
Your Pharma Rep"""
    yield _ok(ACTION_GENERATE_EMAIL, {"hcp_name": doctor}, {"email": email}, tool_used="generate_email_template")


def _resolve_date(date_str: str) -> str:
    date_str = date_str.strip().lower()
    today = datetime.utcnow().date()
    if date_str in ("today", "now"):
        return today.isoformat()
    if date_str in ("tomorrow", "tom"):
        return (today + timedelta(days=1)).isoformat()
    return date_str


_NODE_DISPATCH: dict[str, callable] = {
    ACTION_CREATE_HCP:         _handle_create_hcp,
    ACTION_LOG_INTERACTION:    _handle_log_interaction,
    ACTION_GET_HCP_HISTORY:    _handle_get_hcp_history,
    ACTION_GET_HCP_PROFILE:    _handle_get_hcp_profile,
    ACTION_LIST_HCPS:          _handle_list_hcps,
    ACTION_RECOMMEND_HCPS:     _handle_recommend_hcps,
    ACTION_GET_INACTIVE_HCPS:  _handle_get_inactive_hcps,
    ACTION_GET_FOLLOWUPS:      _handle_get_followups,
    ACTION_GET_DAILY_SUMMARY:  _handle_get_daily_summary,
    ACTION_FILTER_BY_PRIORITY: _handle_filter_by_priority,
    ACTION_CREATE_TAG:         _handle_create_tag,
    ACTION_ASSIGN_TAG:         _handle_assign_tag,
    ACTION_GET_HCP_TAGS:       _handle_get_hcp_tags,
    ACTION_SEARCH_BY_TAG:      _handle_search_by_tag,
    ACTION_BOOK_APPOINTMENT:   _handle_book_appointment,
    ACTION_LIST_APPOINTMENTS:  _handle_list_appointments,
    ACTION_CANCEL_APPOINTMENT: _handle_cancel_appointment,
    ACTION_SEARCH_NOTES:       _handle_search_notes,
    ACTION_GENERATE_SUMMARY:   _handle_generate_summary,
    ACTION_GENERATE_EMAIL:     _handle_generate_email,
}

_DISPATCH = _NODE_DISPATCH


async def run_agent_stream(user_input: str, session_id: str = "default"):
    logger.info(f"Agent invoked: {user_input[:200]} (session={session_id})")
    session = _get_session(session_id)
    session["history"].append({"role": "user", "content": user_input})

    try:
        if rejection := _pre_guard(user_input):
            yield rejection
            return

        pending_action = session.get("pending_action")
        if pending_action and pending_action in _NODE_DISPATCH:
            handler = _NODE_DISPATCH[pending_action]
            merged_params = {**(session.get("pending_params") or {}), "raw_input": user_input}
            async for chunk in handler(merged_params, session=session):
                yield chunk
            return

        classification = await _classify_intent(user_input, session)
        intent = classification.get("intent", "NONE")
        entities = classification.get("entities", {})
        confidence = classification.get("confidence", 0.0)

        params = dict(entities)
        params["raw_input"] = user_input

        # Normalize entity keys: rule classifier uses "doctor"/"tag", handlers use "hcp_name"/"tag_name"
        doctor = params.get("doctor") or params.get("hcp_name") or params.get("name")
        if doctor:
            params["hcp_name"] = doctor
            params["doctor"] = doctor
            session["context"]["last_doctor"] = doctor
        tag = params.get("tag")
        if tag:
            params["tag_name"] = tag
        # If logging interaction but no notes provided, use the raw input as notes
        if intent == ACTION_LOG_INTERACTION and not params.get("notes"):
            params["notes"] = user_input

        handler = _NODE_DISPATCH.get(intent)
        if handler:
            async for chunk in handler(params, session=session, confidence=confidence):
                yield chunk
            session["history"].append({"role": "assistant", "content": f"Executed {intent}"})
            return

        # Try LLM streaming fallback; if Ollama is down, return a dummy response
        try:
            async for chunk in chat_stream(
                messages=[
                    {"role": "system", "content": (
                        "You are a helpful Healthcare Professionals CRM assistant. "
                        "Help users log interactions, find HCPs, check follow-ups, and manage their CRM. "
                        "If the user seems to want to book an appointment or log a meeting, "
                        "ask them: which doctor, and what happened or what date. "
                        "Keep responses concise and actionable."
                    )},
                    {"role": "user", "content": user_input[:1000]},
                ],
                timeout=AGENT_TIMEOUT,
            ):
                yield chunk
        except Exception as e:
            logger.warning(f"LLM fallback failed, using dummy response: {e}")
            yield (
                "I'm a demo CRM assistant. I can help you log interactions, find doctors, "
                "check follow-ups, and manage appointments. Please try a specific command like "
                "'List all doctors' or 'Book Dr. Sharma tomorrow 10:00'."
            )

    except asyncio.TimeoutError:
        logger.error("Agent timed out.")
        yield json.dumps({"action": "ERROR", "status": "timeout",
                          "result": {"message": "⏱️ Request timed out. Please try again in a moment."}})
    except Exception as e:
        logger.error(f"Agent error: {e}")
        yield json.dumps({"action": "ERROR", "status": "error", "result": {"message": "⚠️ AI Agent is temporarily unavailable. Please try again."}})
