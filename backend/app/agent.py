import os
from dotenv import load_dotenv
import json
from groq import Groq
from .db_utils import insert_interaction, get_interactions_by_hcp, get_all_hcp

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

AGENT_PROMPT = """
You are HCP CRM agent.

Tools:
1. log_interaction(hcp_name, notes)
2. get_history(hcp_name)
3. list_hcp()

Respond with JSON:
{
  "tool": "log_interaction|get_history|list_hcp|none",
  "params": {...}
}

Or natural response if "none".

User: {input}
"""

async def run_agent_stream(user_input):
    prompt = AGENT_PROMPT.format(input=user_input)
    
    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    
    full_response = ""
    for chunk in response:
        if chunk.choices[0].delta.content:
            chunk_text = chunk.choices[0].delta.content
            full_response += chunk_text
            yield chunk_text
    
    # Parse tool
    try:
        start = full_response.find('{')
        end = full_response.rfind('}') + 1
        if start != -1:
            json_str = full_response[start:end]
            action = json.loads(json_str)
            tool = action.get("tool")
            params = action.get("params", {})
            
            if tool == "log_interaction":
                insert_interaction(params.get("hcp_name"), params.get("notes", ""))
                yield "\n✅ Logged"
            elif tool == "get_history":
                history = get_interactions_by_hcp(params.get("hcp_name", ""))
                yield "\nHistory: " + str(history)
            elif tool == "list_hcp":
                hcps = get_all_hcp()
                yield "\nHCPs: " + str(hcps)
    except:
        pass

