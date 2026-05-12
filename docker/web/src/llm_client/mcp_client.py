import os
import requests

BASE_URL = os.getenv("BRIDGE_BASE", "http://127.0.0.1:8787")

QUEST_FILE_PATH = os.getenv(
    "QUEST_FILE_PATH",
    "/app/game.quest"
)


def call_tool(name, args):
    if name == "new_game":
        return requests.post(
            f"{BASE_URL}/session/new",
            json={
                "sessionId": "demo",
                "questFilePath": QUEST_FILE_PATH
            }
        ).json()

    if name == "look":
        return requests.post(
            f"{BASE_URL}/session/command",
            json={
                "sessionId": "demo",
                "text": "look"
            }
        ).json()

    if name == "move":
        direction = args.get("direction", "north")
        return requests.post(
            f"{BASE_URL}/session/command",
            json={
                "sessionId": "demo",
                "text": f"go {direction}"
            }
        ).json()

    return {
        "ok": False,
        "error": f"Tool no implementada: {name}"
    }