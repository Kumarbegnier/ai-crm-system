"""LLM-powered AI tools: summary generation, email generation, entity extraction.
All calls route through the local Ollama client.
"""

import json
import logging
import asyncio
from .config import AGENT_MODEL, AGENT_TIMEOUT
from .llm_client import get_client

logger = logging.getLogger(__name__)


async def generate_ai_summary(hcp_name: str, interactions: list[dict]) -> str:
    """Summarize the last N interactions for an HCP."""
    if not interactions:
        return f"No interactions found for {hcp_name}."

    lines = []
    for i, inter in enumerate(interactions[:5], 1):
        lines.append(
            f"{i}. [{inter.get('interaction_date', 'unknown')}] "
            f"{inter.get('interaction_type', 'call')}: {inter['notes']}"
        )
    context = "\n".join(lines)

    prompt = (
        f"You are a CRM AI assistant. Summarize the following interactions with {hcp_name} "
        f"in 2-3 concise bullet points. Focus on key topics discussed, sentiment trends, and any follow-up actions.\n\n"
        f"{context}\n\nSummary:"
    )

    try:
        async with asyncio.timeout(AGENT_TIMEOUT):
            resp = await get_client().chat(
                model=AGENT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
        return resp["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return "⚠️ Could not generate summary at this time."


async def generate_followup_email(hcp_name: str, last_interaction: dict) -> str:
    """Generate a professional follow-up email based on the last interaction."""
    notes = last_interaction.get("notes", "")
    product = last_interaction.get("product_discussed", "")
    outcome = last_interaction.get("outcome", "")

    prompt = (
        f"Write a short, professional follow-up email to {hcp_name} from a pharmaceutical sales rep.\n"
        f"Context from last meeting:\n"
        f"- Notes: {notes}\n"
        f"- Product discussed: {product or 'N/A'}\n"
        f"- Outcome: {outcome or 'N/A'}\n\n"
        f"Requirements:\n"
        f"- Subject line included\n"
        f"- Brief and courteous (under 150 words)\n"
        f"- Include a call to action (schedule next meeting, request feedback, etc.)\n\n"
        f"Email:"
    )

    try:
        async with asyncio.timeout(AGENT_TIMEOUT):
            resp = await get_client().chat(
                model=AGENT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
        return resp["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Email generation failed: {e}")
        return "⚠️ Could not generate email at this time."


async def extract_entities_from_notes(notes: str) -> dict:
    """Extract structured entities (drug, dosage, follow-up date, sentiment) from raw notes."""
    prompt = (
        "You are a medical CRM entity extractor. Extract structured data from the following interaction notes.\n"
        "Output ONLY valid JSON with these keys (use null if not found):\n"
        "{\n"
        '  "drug_mentioned": "string or null",\n'
        '  "dosage_mentioned": "string or null",\n'
        '  "follow_up_date": "YYYY-MM-DD or null",\n'
        '  "sentiment": "positive|neutral|negative",\n'
        '  "topics": ["list", "of", "topics"]\n'
        "}\n\n"
        f"Notes: {notes}\n\nJSON:"
    )

    try:
        async with asyncio.timeout(AGENT_TIMEOUT):
            resp = await get_client().chat(
                model=AGENT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
            )
        text = resp["message"]["content"].strip()
        # Extract JSON fence if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.error(f"Entity extraction failed: {e}")
        return {
            "drug_mentioned": None,
            "dosage_mentioned": None,
            "follow_up_date": None,
            "sentiment": "neutral",
            "topics": [],
        }

