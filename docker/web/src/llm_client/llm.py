import requests
from src.llm_client.config import API_KEY, MODEL, BASE_URL
from src.llm_client.tools import tools


def call_llm(messages, timeout: float = 60.0):
    try:
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
            },
            timeout=timeout,  # sin timeout, un proveedor colgado bloquea la sesion
        )
        return response.json()
    except requests.RequestException as e:      # red caida o timeout
        return {"error": f"LLM_UNREACHABLE: {e}"}
    except ValueError:                          # respuesta que no es JSON (p.ej. 502)
        return {"error": f"LLM_BAD_RESPONSE: HTTP {response.status_code}"}
