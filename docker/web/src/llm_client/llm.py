import requests
from src.llm_client.config import API_KEY, MODEL, BASE_URL
from src.llm_client.tools import tools
def call_llm(messages):
    response = requests.post(
        BASE_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": MODEL,
            "messages": messages,
            "tools": tools
        }
    )

    return response.json()