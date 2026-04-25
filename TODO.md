# AI Agent Behavior Testing & Improvement — Implementation Plan

## Phase 1: Automated Behavior Test Suite
- [x] 1. Create `backend/test_agent_behavior.py` with the exact test matrix
- [x] 2. Add `get_appointment_by_id()` helper in `backend/app/db_utils.py`

## Phase 2: Agent Core Improvements
- [x] 3. Fix CANCEL_APPOINTMENT node to actually cancel appointments
- [x] 4. Add intent confidence scoring to LLM classifier
- [x] 5. Add explainability fields (tool_used, reason, confidence) to all responses
- [x] 6. Improve anaphora resolution ("his", "her", "they") in multi-turn context
- [x] 7. Add tool parameter validation layer

## Phase 3: Frontend & Integration
- [x] 8. Update `frontend/src/contexts/ChatContext.tsx` for new explainability fields

## Phase 4: Validation
- [ ] 9. Run behavior tests and verify all pass
- [ ] 10. Run frontend tests and verify build

