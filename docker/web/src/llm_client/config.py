import os

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
BASE_URL = "https://openrouter.ai/api/v1/chat/completions"