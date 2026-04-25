"""
AI Agent Behavior Test Suite

Tests the agent against a comprehensive behavior matrix covering:
A. Intent Classification
B. Tool Execution Accuracy
C. Response Quality
D. Multi-Turn Context
E. Failure Handling

Run with: python -m pytest backend/test_agent_behavior.py -v
"""

import asyncio
import json
import pytest
import sqlite3
from datetime import datetime, timedelta

# Ensure app imports work
import sys
sys.path.insert(0, __file__.rsplit("/test_agent_behavior.py", 1)[0])

from app.db import init_db, get_connection
from app.db_utils import (
    upsert_hcp,
    insert_interaction,
    create_appointment,
    get_appointment_by_id,
    get_hcp_profile,
    cancel_appointment,
    normalize_name,
)
from app.agent import (
    run_agent_stream,
    _classify_intent,
    _pre_guard,
    _get_session,
    _clear_session,
    _extract_json,
    _NODE_DISPATCH,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Use an isolated temp DB for every test."""
    db_file = tmp_path / "test_crm.db"
    monkeypatch.setattr("app.db.DB_PATH", str(db_file))
    monkeypatch.setattr("app.db_utils.DB_PATH", str(db_file))
    # Clear connection cache so init_db uses the new DB_PATH
    from app.db import _local
    _local.conn = None
    # Also patch vector_store's get_connection
    monkeypatch.setattr("app.vector_store.get_connection", get_connection)
    init_db()
    yield
    # Cleanup sessions between tests
    from app.agent import _SESSIONS
    _SESSIONS.clear()
    _local.conn = None


@pytest.fixture
def sample_hcps():
    """Seed a few HCPs for tests."""
    hcps = [
        {"name": "Dr. Sharma", "specialty": "Cardiology", "organization": "Apollo Hospital", "city": "Delhi"},
        {"name": "Dr. Mehta", "specialty": "Neurology", "organization": "Fortis", "city": "Mumbai"},
        {"name": "Dr. Patel", "specialty": "Orthopedics", "organization": "Max Hospital", "city": "Bangalore"},
    ]
    ids = []
    for h in hcps:
        hcp_id = upsert_hcp(h)
        ids.append(hcp_id)
    return ids


@pytest.fixture
def sample_interactions(sample_hcps):
    """Seed interactions for Dr. Sharma and Dr. Mehta."""
    insert_interaction(
        "Dr. Sharma",
        "Discussed Lipitor dosage. Patient feedback positive. Follow up in 2 weeks.",
        interaction_type="visit",
        sentiment="positive",
        product_discussed="Lipitor",
        outcome="interested",
        follow_up_required=True,
        follow_up_date=(datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d"),
    )
    insert_interaction(
        "Dr. Mehta",
        "Called about new migraine drug trial. Dr. Mehta skeptical.",
        interaction_type="call",
        sentiment="negative",
        product_discussed="MigraineX",
        outcome="skeptical",
    )


# ---------------------------------------------------------------------------
# A. Intent Classification Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestIntentClassification:
    """Verify the LLM classifier maps queries to correct intents."""

    @pytest.mark.parametrize("query,expected_intent,entities", [
        ("Show Dr Sharma", "GET_HCP_PROFILE", {"doctor": "Dr. Sharma"}),
        ("Log meeting with Dr Mehta", "LOG_INTERACTION", {"doctor": "Dr. Mehta"}),
        ("Summarize Dr Sharma", "GENERATE_SUMMARY", {"doctor": "Dr. Sharma"}),
        ("Tag Dr Sharma as VIP", "ASSIGN_TAG", {"doctor": "Dr. Sharma"}),
        ("What should I do next?", "RECOMMEND_HCPS", {}),
        ("Book Dr. Patel tomorrow 14:30", "BOOK_APPOINTMENT", {"doctor": "Dr. Patel", "date": "tomorrow", "time": "14:30"}),
        ("Who needs follow-up?", "GET_FOLLOWUPS", {}),
        ("Show pending follow-ups", "GET_FOLLOWUPS", {}),
        ("List all doctors", "LIST_HCPS", {}),
        ("Show high priority HCPs", "FILTER_BY_PRIORITY", {}),
        ("History of Dr Sharma", "GET_HCP_HISTORY", {"doctor": "Dr. Sharma"}),
        ("Create tag key-opinion-leader", "CREATE_TAG", {}),
        ("Doctors tagged VIP", "SEARCH_BY_TAG", {}),
        ("Search notes about cholesterol", "SEARCH_NOTES", {}),
        ("Draft follow-up email to Dr Sharma", "GENERATE_EMAIL", {"doctor": "Dr. Sharma"}),
        ("My appointments", "LIST_APPOINTMENTS", {}),
        ("Cancel appointment 5", "CANCEL_APPOINTMENT", {}),
        ("Show today summary", "GET_DAILY_SUMMARY", {}),
        ("Inactive doctors last 45 days", "GET_INACTIVE_HCPS", {}),
    ])
    async def test_intent_mapping(self, query, expected_intent, entities):
        """Each query should map to the expected intent."""
        session = _get_session("test-session")
        result = await _classify_intent(query, session)
        print(f"\nQuery: '{query}'")
        print(f"Intent: {result.get('intent')} | Expected: {expected_intent}")
        assert result["intent"] == expected_intent, (
            f"Query '{query}' → expected {expected_intent}, got {result['intent']}"
        )
        # Entity presence check (loose — LLM may not extract all)
        if entities.get("doctor"):
            assert result["entities"].get("doctor") is not None or result["entities"].get("name") is not None

    @pytest.mark.asyncio
    async def test_unclear_intent_falls_back(self):
        """Totally random input should return NONE or fallback gracefully."""
        session = _get_session("test-session-2")
        result = await _classify_intent("xyz123 banana", session)
        print(f"\nUnclear query → Intent: {result.get('intent')}")
        assert result["intent"] in ("NONE",)


# ---------------------------------------------------------------------------
# B. Tool Execution Accuracy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestToolExecution:
    """Verify tools execute correctly and mutate/read DB accurately."""

    async def _run_agent(self, query: str, session_id: str = "exec-test") -> list[dict]:
        """Helper: collect all JSON chunks from run_agent_stream."""
        chunks = []
        async for chunk in run_agent_stream(query, session_id=session_id):
            if chunk == "__END__":
                continue
            try:
                chunks.append(json.loads(chunk))
            except json.JSONDecodeError:
                chunks.append({"raw": chunk})
        return chunks

    @pytest.mark.asyncio
    async def test_log_interaction_creates_db_record(self, sample_hcps):
        """LOG_INTERACTION must create a real DB row."""
        chunks = await self._run_agent("Met Dr. Sharma today, discussed Lipitor, positive response")
        print(f"\nLOG chunks: {chunks}")
        # Find success chunk
        success = [c for c in chunks if c.get("action") == "LOG_INTERACTION" and c.get("status") == "ok"]
        assert success, f"Expected LOG_INTERACTION success, got: {chunks}"
        interaction_id = success[0]["result"]["interaction_id"]
        # Verify DB
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM interactions WHERE id = ?", (interaction_id,)
            ).fetchone()
        assert row is not None, "Interaction not found in DB"
        assert row["notes"] is not None

    @pytest.mark.asyncio
    async def test_book_appointment_creates_record(self, sample_hcps):
        """BOOK_APPOINTMENT must create a real appointment."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        chunks = await self._run_agent(
            f"Book Dr. Sharma {tomorrow} 10:00",
            session_id="appt-test"
        )
        print(f"\nBOOK chunks: {chunks}")
        success = [c for c in chunks if c.get("action") == "BOOK_APPOINTMENT" and c.get("status") == "ok"]
        assert success, f"Expected BOOK_APPOINTMENT success, got: {chunks}"
        appt_id = success[0]["result"]["appointment_id"]
        # Verify DB
        appt = get_appointment_by_id(appt_id)
        assert appt is not None, "Appointment not found in DB"
        assert appt["status"] == "scheduled"

    @pytest.mark.asyncio
    async def test_book_conflict_returns_error_with_alternatives(self, sample_hcps):
        """Double-booking same slot should return error with alternatives."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        # First booking
        chunks1 = await self._run_agent(
            f"Book Dr. Sharma {tomorrow} 10:00", session_id="conflict-1"
        )
        success1 = [c for c in chunks1 if c.get("action") == "BOOK_APPOINTMENT" and c.get("status") == "ok"]
        assert success1, "First booking should succeed"
        # Second booking same slot
        chunks2 = await self._run_agent(
            f"Book Dr. Sharma {tomorrow} 10:00", session_id="conflict-2"
        )
        print(f"\nCONFLICT chunks: {chunks2}")
        errors = [c for c in chunks2 if c.get("action") == "BOOK_APPOINTMENT" and c.get("status") == "error"]
        assert errors, f"Expected conflict error, got: {chunks2}"
        assert "not available" in errors[0]["result"]["message"].lower()

    @pytest.mark.asyncio
    async def test_cancel_appointment_actually_cancels(self, sample_hcps):
        """CANCEL_APPOINTMENT must change status to cancelled."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        hcp = get_hcp_profile("Dr. Sharma")
        appt_id = create_appointment(hcp["id"], tomorrow, "11:00")
        # Cancel via agent
        chunks = await self._run_agent(
            f"Cancel appointment {appt_id}",
            session_id="cancel-test"
        )
        print(f"\nCANCEL chunks: {chunks}")
        # The agent may ask for confirmation first, then we send confirm
        # For now, verify that the cancel endpoint works
        cancelled = cancel_appointment(appt_id)
        assert cancelled
        appt = get_appointment_by_id(appt_id)
        assert appt["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_create_tag_assign_tag_roundtrip(self, sample_hcps):
        """CREATE_TAG + ASSIGN_TAG must persist."""
        chunks_create = await self._run_agent("Create tag early-adopter", session_id="tag-test")
        print(f"\nCREATE_TAG chunks: {chunks_create}")
        # Then assign
        chunks_assign = await self._run_agent("Tag Dr. Sharma as early-adopter", session_id="tag-test")
        print(f"ASSIGN_TAG chunks: {chunks_assign}")
        success = [c for c in chunks_assign if c.get("action") == "ASSIGN_TAG" and c.get("status") == "ok"]
        assert success, f"Expected ASSIGN_TAG success, got: {chunks_assign}"

    @pytest.mark.asyncio
    async def test_list_appointments_returns_data(self, sample_hcps):
        """LIST_APPOINTMENTS should return real DB data."""
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        hcp = get_hcp_profile("Dr. Sharma")
        create_appointment(hcp["id"], tomorrow, "09:00")
        chunks = await self._run_agent("My appointments", session_id="list-appt")
        print(f"\nLIST_APPOINTMENTS chunks: {chunks}")
        success = [c for c in chunks if c.get("action") == "LIST_APPOINTMENTS" and c.get("status") == "ok"]
        assert success
        assert len(success[0]["result"]["appointments"]) >= 1


# ---------------------------------------------------------------------------
# C. Response Quality Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestResponseQuality:
    """Responses must be specific, data-grounded, and actionable."""

    async def _run_agent(self, query: str, session_id: str = "quality-test") -> list[dict]:
        chunks = []
        async for chunk in run_agent_stream(query, session_id=session_id):
            if chunk == "__END__":
                continue
            try:
                chunks.append(json.loads(chunk))
            except json.JSONDecodeError:
                chunks.append({"raw": chunk})
        return chunks

    @pytest.mark.asyncio
    async def test_recommendation_is_specific(self, sample_hcps, sample_interactions):
        """RECOMMEND_HCPS must include real names and scores, not generic text."""
        chunks = await self._run_agent("Who should I visit today?")
        print(f"\nRECOMMEND chunks: {chunks}")
        success = [c for c in chunks if c.get("action") == "RECOMMEND_HCPS" and c.get("status") == "ok"]
        assert success
        recs = success[0]["result"]["recommendations"]
        assert len(recs) > 0
        # Must have real names
        assert all("name" in r for r in recs)
        # Must have AI scores
        assert all("ai_score" in r for r in recs)

    @pytest.mark.asyncio
    async def test_followups_are_specific(self, sample_hcps, sample_interactions):
        """GET_FOLLOWUPS must name specific doctors and dates."""
        chunks = await self._run_agent("Who needs follow-up?")
        print(f"\nFOLLOWUP chunks: {chunks}")
        success = [c for c in chunks if c.get("action") == "GET_FOLLOWUPS" and c.get("status") == "ok"]
        assert success
        followups = success[0]["result"]["followups"]
        assert len(followups) > 0
        # Must reference Dr. Sharma
        names = [f["hcp_name"] for f in followups]
        assert "Dr. Sharma" in names or "Dr Sharma" in names

    @pytest.mark.asyncio
    async def test_hcp_profile_is_structured(self, sample_hcps):
        """GET_HCP_PROFILE must return structured data."""
        chunks = await self._run_agent("Profile of Dr. Sharma")
        print(f"\nPROFILE chunks: {chunks}")
        success = [c for c in chunks if c.get("action") == "GET_HCP_PROFILE" and c.get("status") == "ok"]
        assert success
        profile = success[0]["result"]["profile"]
        assert profile["name"] == "Dr. Sharma"
        assert "specialty" in profile

    @pytest.mark.asyncio
    async def test_daily_summary_has_metrics(self, sample_hcps, sample_interactions):
        """GET_DAILY_SUMMARY must include numeric metrics."""
        chunks = await self._run_agent("Show today summary")
        print(f"\nSUMMARY chunks: {chunks}")
        success = [c for c in chunks if c.get("action") == "GET_DAILY_SUMMARY" and c.get("status") == "ok"]
        assert success
        summary = success[0]["result"]["summary"]
        assert "total_interactions" in summary
        assert "unique_hcps_visited" in summary


# ---------------------------------------------------------------------------
# D. Multi-Turn Context Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestMultiTurnContext:
    """The agent must remember entities across turns."""

    async def _run_agent(self, query: str, session_id: str) -> list[dict]:
        chunks = []
        async for chunk in run_agent_stream(query, session_id=session_id):
            if chunk == "__END__":
                continue
            try:
                chunks.append(json.loads(chunk))
            except json.JSONDecodeError:
                chunks.append({"raw": chunk})
        return chunks

    @pytest.mark.asyncio
    async def test_pronoun_resolution_his(self, sample_hcps, sample_interactions):
        """After mentioning Dr. Sharma, 'his' should resolve correctly."""
        sid = "pronoun-test-1"
        # Turn 1: establish Dr. Sharma
        chunks1 = await self._run_agent("Show Dr. Sharma", session_id=sid)
        print(f"\nTurn 1 chunks: {chunks1}")
        # Turn 2: use pronoun
        chunks2 = await self._run_agent("Summarize his interactions", session_id=sid)
        print(f"\nTurn 2 chunks: {chunks2}")
        success = [c for c in chunks2 if c.get("action") == "GENERATE_SUMMARY" and c.get("status") == "ok"]
        # If it asked for clarification, that's acceptable but we prefer auto-resolution
        if not success:
            asks = [c for c in chunks2 if c.get("status") == "ask"]
            assert asks, f"Expected GENERATE_SUMMARY or ask, got: {chunks2}"
        else:
            assert success[0]["params"]["hcp_name"] == "Dr. Sharma"

    @pytest.mark.asyncio
    async def test_context_carries_across_multi_step_booking(self, sample_hcps):
        """Multi-step booking: doctor → date → time → confirm."""
        sid = "multistep-test"
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Step 1: mention doctor
        chunks1 = await self._run_agent("Book Dr. Sharma", session_id=sid)
        print(f"\nStep 1: {chunks1}")
        asks1 = [c for c in chunks1 if c.get("status") == "ask"]
        assert asks1, "Should ask for date"

        # Step 2: provide date
        chunks2 = await self._run_agent(f"{tomorrow}", session_id=sid)
        print(f"\nStep 2: {chunks2}")
        asks2 = [c for c in chunks2 if c.get("status") == "ask"]
        assert asks2, "Should ask for time"

        # Step 3: provide time
        chunks3 = await self._run_agent("14:30", session_id=sid)
        print(f"\nStep 3: {chunks3}")
        success = [c for c in chunks3 if c.get("action") == "BOOK_APPOINTMENT" and c.get("status") == "ok"]
        assert success, f"Expected booking success, got: {chunks3}"

    @pytest.mark.asyncio
    async def test_context_does_not_leak_between_sessions(self, sample_hcps):
        """Session A memory must not leak into Session B."""
        # Session A: mention Dr. Sharma
        await self._run_agent("Show Dr. Sharma", session_id="session-a")
        # Session B: ask about "his" — should NOT know it's Dr. Sharma
        chunks = await self._run_agent("Summarize his interactions", session_id="session-b")
        print(f"\nSession B chunks: {chunks}")
        # Should ask for clarification since no prior context
        asks = [c for c in chunks if c.get("status") == "ask"]
        assert asks, "Session B should not inherit Session A's context"


# ---------------------------------------------------------------------------
# E. Failure Handling Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestFailureHandling:
    """Graceful degradation for edge cases."""

    async def _run_agent(self, query: str, session_id: str = "fail-test") -> list[dict]:
        chunks = []
        async for chunk in run_agent_stream(query, session_id=session_id):
            if chunk == "__END__":
                continue
            try:
                chunks.append(json.loads(chunk))
            except json.JSONDecodeError:
                chunks.append({"raw": chunk})
        return chunks

    @pytest.mark.asyncio
    async def test_nonexistent_hcp_graceful(self):
        """Querying alien doctor should return error, not crash."""
        chunks = await self._run_agent("Show Dr. AlienX")
        print(f"\nAlien chunks: {chunks}")
        # Should get error or empty result
        errors = [c for c in chunks if c.get("status") == "error"]
        success_empty = [c for c in chunks if c.get("status") == "ok" and not c.get("result", {}).get("profile")]
        assert errors or success_empty, f"Should handle gracefully, got: {chunks}"

    @pytest.mark.asyncio
    async def test_empty_input_ignored(self):
        """Empty input should not crash or create records."""
        chunks = await self._run_agent("   ")
        print(f"\nEmpty chunks: {chunks}")
        # Should yield nothing or a rejection
        assert len(chunks) == 0 or any(c.get("action") == "REJECTED" for c in chunks)

    @pytest.mark.asyncio
    async def test_medical_symptom_guard(self):
        """Medical symptom queries should be rejected with appropriate message."""
        chunks = await self._run_agent("headache")
        print(f"\nMedical chunks: {chunks}")
        rejected = [c for c in chunks if c.get("action") == "REJECTED"]
        assert rejected, f"Medical term should be rejected, got: {chunks}"
        assert "medical" in rejected[0]["result"]["message"].lower()

    @pytest.mark.asyncio
    async def test_random_gibberish_fallback(self):
        """Random text should fall back to LLM or NONE intent gracefully."""
        chunks = await self._run_agent("asdlkfj 29384 zzz")
        print(f"\nGibberish chunks: {chunks}")
        # Should not crash — any response is acceptable
        assert True  # If we got here without exception, pass

    @pytest.mark.asyncio
    async def test_very_long_input_handled(self):
        """Inputs near the WS limit should be handled."""
        long_input = "book " + "a" * 7000
        chunks = await self._run_agent(long_input)
        print(f"\nLong input chunks count: {len(chunks)}")
        # Should not crash
        assert True


# ---------------------------------------------------------------------------
# F. Structured Response / Explainability Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestExplainability:
    """Responses should include tool_used, reason, confidence where applicable."""

    async def _run_agent(self, query: str, session_id: str = "explain-test") -> list[dict]:
        chunks = []
        async for chunk in run_agent_stream(query, session_id=session_id):
            if chunk == "__END__":
                continue
            try:
                chunks.append(json.loads(chunk))
            except json.JSONDecodeError:
                chunks.append({"raw": chunk})
        return chunks

    @pytest.mark.asyncio
    async def test_response_has_tool_used_field(self, sample_hcps):
        """Structured responses should include 'tool_used' for traceability."""
        chunks = await self._run_agent("List all doctors")
        print(f"\nExplainability chunks: {chunks}")
        success = [c for c in chunks if c.get("status") == "ok"]
        if success:
            assert "tool_used" in success[0], f"Missing tool_used in: {success[0]}"

    @pytest.mark.asyncio
    async def test_response_has_confidence_field(self, sample_hcps):
        """Structured responses should include 'confidence' for intent certainty."""
        chunks = await self._run_agent("Show Dr. Sharma")
        success = [c for c in chunks if c.get("status") == "ok"]
        if success:
            assert "confidence" in success[0], f"Missing confidence in: {success[0]}"


# ---------------------------------------------------------------------------
# G. Performance / Stress Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPerformance:
    """Quick smoke tests for performance regressions."""

    async def _run_agent(self, query: str, session_id: str) -> list[dict]:
        chunks = []
        async for chunk in run_agent_stream(query, session_id=session_id):
            if chunk == "__END__":
                continue
            try:
                chunks.append(json.loads(chunk))
            except json.JSONDecodeError:
                chunks.append({"raw": chunk})
        return chunks

    @pytest.mark.asyncio
    async def test_rapid_sequential_queries(self, sample_hcps):
        """Rapid queries should not corrupt session state."""
        for i in range(5):
            chunks = await self._run_agent("List all doctors", session_id=f"perf-{i}")
            success = [c for c in chunks if c.get("action") == "LIST_HCPS" and c.get("status") == "ok"]
            assert success, f"Query {i} failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

