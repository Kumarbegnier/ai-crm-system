"""
Pydantic-based tool schemas for the CRM agent.
Provides structured descriptions that can be fed to an LLM for function calling.
"""
from typing import Any
from pydantic import BaseModel, Field


class ToolParam(BaseModel):
    name: str
    type: str
    description: str
    required: bool = True


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: list[ToolParam]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="CREATE_HCP",
        description="Create or update a healthcare professional (HCP) profile.",
        parameters=[
            ToolParam(name="name", type="string", description="Full name of the doctor, e.g. 'Dr. Sharma'"),
            ToolParam(name="specialty", type="string", description="Medical specialty", required=False),
            ToolParam(name="organization", type="string", description="Hospital or clinic name", required=False),
            ToolParam(name="city", type="string", description="City", required=False),
        ],
    ),
    ToolDefinition(
        name="LOG_INTERACTION",
        description="Log a sales rep interaction (visit, call, email) with a doctor.",
        parameters=[
            ToolParam(name="hcp_name", type="string", description="Doctor name"),
            ToolParam(name="notes", type="string", description="What was discussed"),
            ToolParam(name="interaction_type", type="string", description="visit | call | email | other", required=False),
            ToolParam(name="product_discussed", type="string", description="Drug or product name", required=False),
            ToolParam(name="outcome", type="string", description="interested | skeptical | neutral | other", required=False),
            ToolParam(name="follow_up_required", type="boolean", description="Whether follow-up is needed", required=False),
            ToolParam(name="follow_up_date", type="string", description="YYYY-MM-DD", required=False),
        ],
    ),
    ToolDefinition(
        name="GET_HCP_PROFILE",
        description="Show a doctor's full CRM profile.",
        parameters=[
            ToolParam(name="hcp_name", type="string", description="Doctor name"),
        ],
    ),
    ToolDefinition(
        name="GET_HCP_HISTORY",
        description="Show interaction history for a specific doctor.",
        parameters=[
            ToolParam(name="hcp_name", type="string", description="Doctor name"),
        ],
    ),
    ToolDefinition(
        name="LIST_HCPS",
        description="List all doctors in the CRM.",
        parameters=[],
    ),
    ToolDefinition(
        name="RECOMMEND_HCPS",
        description="AI-recommend which doctors to visit today based on recency and frequency.",
        parameters=[
            ToolParam(name="limit", type="integer", description="Number of recommendations", required=False),
        ],
    ),
    ToolDefinition(
        name="GET_INACTIVE_HCPS",
        description="Find doctors with no recent interactions.",
        parameters=[
            ToolParam(name="days", type="integer", description="Inactive threshold in days", required=False),
        ],
    ),
    ToolDefinition(
        name="FILTER_BY_PRIORITY",
        description="Filter doctors by priority (high / medium / low).",
        parameters=[
            ToolParam(name="priority", type="string", description="high | medium | low"),
        ],
    ),
    ToolDefinition(
        name="GET_FOLLOWUPS",
        description="List all pending follow-ups.",
        parameters=[],
    ),
    ToolDefinition(
        name="GET_DAILY_SUMMARY",
        description="Show today's activity summary (interactions, visits, top HCP).",
        parameters=[],
    ),
    ToolDefinition(
        name="CREATE_TAG",
        description="Create a new tag or label.",
        parameters=[
            ToolParam(name="name", type="string", description="Tag name"),
            ToolParam(name="category", type="string", description="e.g. 'segment', 'behavior'", required=False),
        ],
    ),
    ToolDefinition(
        name="ASSIGN_TAG",
        description="Assign a tag to a doctor.",
        parameters=[
            ToolParam(name="hcp_name", type="string", description="Doctor name"),
            ToolParam(name="tag_name", type="string", description="Tag name"),
        ],
    ),
    ToolDefinition(
        name="GET_HCP_TAGS",
        description="Show tags assigned to a doctor.",
        parameters=[
            ToolParam(name="hcp_name", type="string", description="Doctor name"),
        ],
    ),
    ToolDefinition(
        name="SEARCH_BY_TAG",
        description="Find doctors with a specific tag.",
        parameters=[
            ToolParam(name="tag_name", type="string", description="Tag name"),
        ],
    ),
    ToolDefinition(
        name="BOOK_APPOINTMENT",
        description="Book an appointment with a doctor.",
        parameters=[
            ToolParam(name="doctor", type="string", description="Doctor name"),
            ToolParam(name="date", type="string", description="YYYY-MM-DD or 'today'/'tomorrow'"),
            ToolParam(name="time", type="string", description="HH:MM 24-hour format"),
            ToolParam(name="notes", type="string", description="Optional notes", required=False),
        ],
    ),
    ToolDefinition(
        name="LIST_APPOINTMENTS",
        description="List appointments.",
        parameters=[
            ToolParam(name="doctor", type="string", description="Filter by doctor", required=False),
            ToolParam(name="date", type="string", description="Filter by date", required=False),
            ToolParam(name="status", type="string", description="scheduled | cancelled", required=False),
        ],
    ),
    ToolDefinition(
        name="CANCEL_APPOINTMENT",
        description="Cancel an appointment by ID.",
        parameters=[
            ToolParam(name="appointment_id", type="integer", description="Appointment ID number"),
        ],
    ),
    ToolDefinition(
        name="SEARCH_NOTES",
        description="Search interaction notes for a keyword.",
        parameters=[
            ToolParam(name="query", type="string", description="Keyword or phrase"),
        ],
    ),
    ToolDefinition(
        name="GENERATE_SUMMARY",
        description="Summarize a doctor's recent interactions.",
        parameters=[
            ToolParam(name="doctor", type="string", description="Doctor name"),
        ],
    ),
    ToolDefinition(
        name="GENERATE_EMAIL",
        description="Draft a follow-up email to a doctor.",
        parameters=[
            ToolParam(name="doctor", type="string", description="Doctor name"),
        ],
    ),
]


# Build a flat lookup for runtime
_TOOL_BY_NAME: dict[str, ToolDefinition] = {t.name: t for t in TOOLS}


def get_tool(name: str) -> ToolDefinition | None:
    return _TOOL_BY_NAME.get(name)


def build_llm_tool_prompt() -> str:
    """Return a compact string of all tool descriptions for LLM system prompts."""
    lines = [
        "You are a CRM assistant with access to the following tools.",
        "Respond ONLY with a JSON object: {\"intent\": \"<TOOL_NAME>\", \"entities\": {...}, \"confidence\": 0.0-1.0}.",
        "If no tool matches, use intent=\"NONE\".",
        "Available tools:\n",
    ]
    for t in TOOLS:
        lines.append(f"- {t.name}: {t.description}")
        for p in t.parameters:
            req = "required" if p.required else "optional"
            lines.append(f"    • {p.name} ({p.type}, {req}): {p.description}")
    return "\n".join(lines)

