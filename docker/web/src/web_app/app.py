"""Interfaz web Flask: chat en lenguaje natural sobre los motores de aventura.

El LLM actua de NARRADOR: traduce la intencion del usuario a tool calls y narra
en espanol el resultado real del motor (que es la fuente de verdad).

Robustez: lock por sesion + auto-reparacion del historial (evita el 400
"tool_calls must be followed by tool messages"). Sesion por usuario (cookie).
Logging opcional (DEBUG_LLM=1). Ruta /reset para empezar de cero.
"""
import os
import json
import uuid
import threading

from flask import Flask, render_template, request, session, redirect, url_for

from src.llm_client.llm import call_llm
from src.llm_client.mcp_client import call_tool

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "tfg-dev-secret-change-me")

MAX_STEPS = int(os.getenv("LLM_MAX_STEPS", "6"))
DEBUG_LLM = os.getenv("DEBUG_LLM", "0") == "1"


def _log(*a):
    if DEBUG_LLM:
        print("[web]", *a, flush=True)


SYSTEM_PROMPT = {
    "role": "system",
    "content": (
        "Eres el NARRADOR de una aventura conversacional. El usuario juega en "
        "lenguaje natural (espanol) y tu eres su interfaz con el juego.\n"
        "\n"
        "TU TRABAJO:\n"
        "1) Interpreta lo que quiere hacer el usuario y ejecutalo con las tools.\n"
        "2) Traduce su intencion al comando del juego (en ingles) y mandalo con "
        "send_game_command: 'coge la linterna' -> 'take lantern'; 've al norte' -> "
        "'north'; 'abre el buzon' -> 'open mailbox'.\n"
        "3) Narra el RESULTADO real del motor en espanol, de forma inmersiva.\n"
        "\n"
        "REGLAS DE ESTILO (MUY IMPORTANTE):\n"
        "- NUNCA muestres comandos del juego ni listas de comandos. Prohibido decir "
        "'tienes disponible TAKE LANTERN' o 'comandos: look, north...'.\n"
        "- Describe la SITUACION como un narrador. En vez de 'comando TAKE LANTERN "
        "disponible', di 'hay una linterna posada sobre la mesa'.\n"
        "- Traduce la salida tecnica (exits, listas de objetos, 'north/south/east/"
        "west') a prosa natural: 'puedes ir al norte o al este', 'ves un pequeno buzon'.\n"
        "- El motor es la FUENTE DE VERDAD: no inventes objetos, salidas ni "
        "resultados. Si dudas, averigualo con look o send_game_command antes de afirmarlo.\n"
        "- Tono de aventura, claro y breve; invita a actuar sin enumerar comandos.\n"
        "\n"
        "MENU: list_games (ver juegos), start_game(game_id) con el id EXACTO del "
        "catalogo (si no lo sabes, llama antes a list_games), current_game, close_game. "
        "Si el usuario solo saluda o pregunta algo general, responde con normalidad."
    ),
}

_STATE: dict[str, dict] = {}
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _state(sid: str) -> dict:
    if sid not in _STATE:
        _STATE[sid] = {"messages": [dict(SYSTEM_PROMPT)], "chat": []}
    return _STATE[sid]


def _lock_for(sid: str) -> threading.Lock:
    with _LOCKS_GUARD:
        if sid not in _LOCKS:
            _LOCKS[sid] = threading.Lock()
        return _LOCKS[sid]


def _repair_history(messages: list) -> list:
    """Cada assistant con tool_calls debe ir seguido de una respuesta 'tool' por
    cada tool_call_id. Repara historiales corrompidos insertando stubs."""
    repaired: list = []
    n = len(messages)
    i = 0
    while i < n:
        m = messages[i]
        repaired.append(m)
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("tool_calls"):
            ids = [tc.get("id") for tc in m["tool_calls"] if isinstance(tc, dict) and tc.get("id")]
            answered = set()
            j = i + 1
            while j < n and isinstance(messages[j], dict) and messages[j].get("role") == "tool":
                repaired.append(messages[j])
                answered.add(messages[j].get("tool_call_id"))
                j += 1
            for cid in ids:
                if cid not in answered:
                    repaired.append({
                        "role": "tool",
                        "tool_call_id": cid,
                        "content": json.dumps({"ok": False, "error": "respuesta_reparada"},
                                              ensure_ascii=False),
                    })
            i = j
            continue
        i += 1
    return repaired


def run_llm_tool_loop(sid: str, max_steps: int = MAX_STEPS) -> str:
    st = _state(sid)

    for step in range(max_steps):
        st["messages"] = _repair_history(st["messages"])
        response = call_llm(st["messages"])

        if isinstance(response, dict) and "error" in response and "choices" not in response:
            _log("LLM error:", response.get("error"))
            return f"Error en la llamada al LLM: {response['error']}"

        choices = response.get("choices", [])
        if not choices:
            return "Error: el modelo no devolvio 'choices'."

        msg = choices[0].get("message", {})

        if not msg.get("tool_calls"):
            st["messages"].append(msg)
            return msg.get("content") or "Sin respuesta."

        st["messages"].append(msg)
        for tool_call in msg["tool_calls"]:
            try:
                tool_name = tool_call["function"]["name"]
            except Exception:
                tool_name = ""
            try:
                tool_args = json.loads(tool_call["function"].get("arguments", "{}") or "{}")
            except Exception:
                tool_args = {}

            _log(f"step {step+1} tool:", tool_name, tool_args)
            try:
                result = call_tool(tool_name, tool_args, session_id=sid)
            except Exception as e:
                result = {"ok": False, "error": str(e)}
            _log("  ->", json.dumps(result, ensure_ascii=False)[:300])

            st["messages"].append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", ""),
                "content": json.dumps(result, ensure_ascii=False),
            })

    return ("He ejecutado varias herramientas pero el modelo no produjo una "
            "respuesta final (posible bucle de tool-calls).")


def _current(sid: str) -> dict:
    try:
        return call_tool("current_game", {}, session_id=sid)
    except Exception:
        return {"active": False}


@app.route("/", methods=["GET", "POST"])
def index():
    if "sid" not in session:
        session["sid"] = uuid.uuid4().hex
    sid = session["sid"]
    st = _state(sid)

    if request.method == "POST":
        user_input = request.form.get("message", "").strip()
        if user_input:
            with _lock_for(sid):
                st["chat"].append({"role": "user", "content": user_input})
                st["messages"].append({"role": "user", "content": user_input})
                final_text = run_llm_tool_loop(sid)
                st["chat"].append({"role": "assistant", "content": final_text})

    return render_template("index.html", messages=st["chat"], current=_current(sid))


@app.route("/reset", methods=["POST"])
def reset():
    sid = session.get("sid")
    if sid:
        with _lock_for(sid):
            try:
                call_tool("close_game", {}, session_id=sid)
            except Exception:
                pass
            _STATE.pop(sid, None)
        _log("session reset:", sid)
    return redirect(url_for("index"))


if __name__ == "__main__":
    # El depurador de Werkzeug permite ejecutar codigo desde el navegador: solo
    # se activa si se pide explicitamente (FLASK_DEBUG=1), nunca por defecto.
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG", "0") == "1")
