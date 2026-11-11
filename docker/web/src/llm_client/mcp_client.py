import os
import requests

BASE_URL = os.getenv("BRIDGE_BASE", "http://127.0.0.1:8787")

QUEST_FILE_PATH = os.getenv(
    "QUEST_FILE_PATH",
    "/app/game.quest"
)


def send_command(text):
    return requests.post(
        f"{BASE_URL}/session/command",
        json={
            "sessionId": "demo",
            "text": text
        }
    ).json()


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
        return send_command("look")

    if name == "move":
        direction = args.get("direction", "north")
        return send_command(f"go {direction}")

    if name == "inventory":
        return send_command("inventory")

    if name == "examine":
        target = args.get("target", "")
        return send_command(f"examine {target}")

    if name == "take":
        item = args.get("item", "")
        return send_command(f"take {item}")

    if name == "drop":
        item = args.get("item", "")
        return send_command(f"drop {item}")

    if name == "use":
        item = args.get("item", "")
        target = args.get("target", "")

        if target:
            return send_command(f"use {item} on {target}")

        return send_command(f"use {item}")

    if name == "open":
        target = args.get("target", "")
        return send_command(f"open {target}")

    if name == "close":
        target = args.get("target", "")
        return send_command(f"close {target}")

    if name == "read":
        target = args.get("target", "")
        return send_command(f"read {target}")

    return {
        "ok": False,
        "error": f"Tool no implementada: {name}"
    }