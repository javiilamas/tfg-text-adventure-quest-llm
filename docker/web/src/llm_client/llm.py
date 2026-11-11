import os
import requests


API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "new_game",
            "description": "Inicia una nueva partida en Quest Viva.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "look",
            "description": "Mira alrededor y describe la ubicación actual del jugador.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move",
            "description": "Mueve al jugador en una dirección concreta.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": "Dirección a la que moverse, por ejemplo north, south, east, west, in u out."
                    }
                },
                "required": ["direction"]
            }
        }
    }
]


def call_llm(messages):
    if not API_KEY:
        return {
            "error": "Falta OPENROUTER_API_KEY. Revisa el archivo .env o las variables de entorno."
        }

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto"
    }

    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=payload,
            timeout=60
        )

        return response.json()

    except Exception as e:
        return {
            "error": str(e)
        }