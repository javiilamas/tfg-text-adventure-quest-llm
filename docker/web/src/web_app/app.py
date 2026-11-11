"""Interfaz web Flask: chat en lenguaje natural sobre los motores de aventura.

Flujo: usuario -> LLM -> (tool calls controladas) -> motor -> resultado real ->
role="tool" -> LLM -> respuesta final. El LLM NUNCA inventa el resultado del
juego; cada motor es la fuente de verdad.

Mejoras respecto a la version anterior:
  * Bucle multi-tool (run_llm_tool_loop) con max_steps: encadena varias tools
    (p.ej. start_game -> look) respondiendo a CADA tool_call_id, evitando el
    error "assistant message with tool_calls must be followed by tool messages".
  * Sesion POR USUARIO (cookie Flask), no un unico estado global.
"""
import os
import json
import uuid

from flask import Flask, render_template, request, session

from src.llm_client.llm import call_llm
from src.llm_client.mcp_client import call_tool

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "tfg-dev-secret-change-me")

MAX_STEPS = int(os.getenv("LLM_MAX_STEPS", "6"))

SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "Eres un asistente que permite jugar a aventuras conversacionales en "
        "lenguaje natural. Hay varios motores (Quest y Frotz/Z-machine) y varios "
        "juegos. Tu NO controlas el estado del juego ni inventas resultados: usas "
        "siempre las herramientas y el motor es la fuente de verdad.\n"
        "- Si el usuario quiere elegir o saber a que jugar, usa list_games.\n"
        "- Para empezar un juego usa start_game(game_id).\n"
        "- Para jugar usa send_game_command con el comando en el dialecto del juego "
        "(p.ej. 'open mailbox', 'east', 'read leaflet'); look y move son atajos.\n"
        "- current_game indica que esta activo; close_game cierra la partida.\n"
        "Tras ejecutar una accion, resume en lenguaje natural la salida real del "
        "motor. Si el usuario solo saluda, responde con normalidad."
    ),
}

# Estado por sesion de navegador: sid -> {"messages": [...], "chat": [...]}
_STATE: dict[str, dict] = {}


def _state(sid: str) -> dict:
    if sid not in _STATE:
        _STATE[sid] = {"messages": [dict(SYSTEM_PROMPT)], "chat": []}
    return _STATE[sid]


def run_llm_tool_loop(sid: str, max_steps: int = MAX_STEPS) -> str:
    messages = _state(sid)["messages"]

    for _ in range(max_steps):
        response = call_llm(messages)

        if isinstance(response, dict) and "error" in response and "choices" not in response:
            return f"Error en la llamada al LLM: {response['error']}"

        choices = response.get("choices", [])
        if not choices:
            return "Error: el modelo no devolvio 'choices'."

        msg = choices[0].get("message", {})

        # Sin tool_calls -> respuesta final
        if not msg.get("tool_calls"):
            messages.append(msg)
            return msg.get("content") or "Sin respuesta."

        # Hay tool_calls: hay que responder a CADA tool_call_id
        messages.append(msg)
        for tool_call in msg["tool_calls"]:
            tool_name = tool_call["function"]["name"]
            try:
                tool_args = json.loads(tool_call["function"].get("arguments", "{}") or "{}")
            except Exception:
                tool_args = {}

            try:
                result = call_tool(tool_name, tool_args, session_id=sid)
            except Exception as e:
                result = {"ok": False, "error": str(e)}

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

    return ("He ejecutado varias herramientas pero el modelo no produjo una "
            "respuesta final (posible bucle de tool-calls).")


@app.route("/", methods=["GET", "POST"])
def index():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    sid = session["sid"]
    st = _state(sid)

    if request.method == "POST":
        user_input = request.form.get("message", "").strip()
        if user_input:
            st["chat"].append({"role": "user", "content": user_input})
            st["messages"].append({"role": "user", "content": user_input})
            final_text = run_llm_tool_loop(sid)
            st["chat"].append({"role": "assistant", "content": final_text})

    return render_template("index.html", messages=st["chat"])


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
