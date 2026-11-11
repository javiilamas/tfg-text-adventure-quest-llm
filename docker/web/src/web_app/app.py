import json
import threading
from flask import Flask, render_template, request, redirect, url_for

from src.llm_client.llm import call_llm
from src.llm_client.mcp_client import call_tool


app = Flask(__name__)

chat_history = []

messages = [
    {
        "role": "system",
        "content": (
            "Eres un agente que juega a una aventura de texto. "
            "Puedes usar herramientas como new_game, look y move cuando sea necesario. "
            "Si el usuario solo saluda o pregunta algo normal, responde directamente. "
            "Cuando inicies una partida, usa new_game y después usa look para describir "
            "el estado inicial. "
            "No inventes el estado del juego: basa tu respuesta en el resultado de las herramientas."
        )
    }
]

conversation_lock = threading.Lock()


def reset_messages():
    global messages, chat_history

    chat_history = []

    messages = [
        {
            "role": "system",
            "content": (
                "Eres un agente que juega a una aventura de texto. "
                "Puedes usar herramientas como new_game, look, move, inventory, examine, take, drop, use, open, close y read. "
                "El usuario puede hablar en lenguaje natural, pero tú debes convertir sus intenciones en herramientas del juego. "
                "No inventes el estado del juego: basa tu respuesta en el resultado real de las herramientas. "
                "Si el usuario pide iniciar la partida, usa new_game y después look. "
                "Si el usuario pide mirar alrededor, usa look. "
                "Si el usuario pide ir a una dirección, usa move. "
                "Si el usuario pide mirar un objeto concreto, usa examine. "
                "Si el usuario pide coger algo, usa take. "
                "Si el usuario pide usar algo, usa use."
            )
        }
    ]


def run_llm_tool_loop(max_steps=5):
    global messages

    for step in range(max_steps):
        response = call_llm(messages)

        print("=" * 80, flush=True)
        print(f"RESPUESTA LLM PASO {step + 1}", flush=True)
        print(json.dumps(response, ensure_ascii=False, indent=2), flush=True)

        if "error" in response:
            return f"Error en llamada al LLM: {response['error']}"

        choices = response.get("choices", [])
        if not choices:
            return "Error: el modelo no devolvió choices."

        msg = choices[0].get("message", {})
        if not msg:
            return "Error: el modelo no devolvió message."

        tool_calls = msg.get("tool_calls")

        if not tool_calls:
            messages.append(msg)
            return msg.get("content") or "Sin respuesta final del modelo."

        messages.append(msg)

        for tool_call in tool_calls:
            tool_call_id = tool_call["id"]
            function = tool_call.get("function", {})
            tool_name = function.get("name")
            raw_args = function.get("arguments", "{}")

            try:
                args = json.loads(raw_args)
            except Exception:
                args = {}

            print("-" * 80, flush=True)
            print(f"TOOL CALL: {tool_name}", flush=True)
            print(f"ARGS: {args}", flush=True)

            try:
                result = call_tool(tool_name, args)
            except Exception as e:
                result = {
                    "ok": False,
                    "error": str(e)
                }

            print("RESULTADO TOOL:", flush=True)
            print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

            tool_message = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(result, ensure_ascii=False)
            }

            messages.append(tool_message)

            print("MENSAJE TOOL AÑADIDO AL HISTORIAL:", flush=True)
            print(json.dumps(tool_message, ensure_ascii=False, indent=2), flush=True)

    return (
        "He ejecutado varias herramientas, pero el modelo no ha producido "
        "una respuesta final. Posible bucle de tool-calls."
    )


@app.route("/", methods=["GET", "POST"])
def index():
    global messages, chat_history

    if request.method == "POST":
        user_input = request.form.get("message", "").strip()

        if not user_input:
            return redirect(url_for("index"))

        with conversation_lock:
            chat_history.append(
                {
                    "role": "user",
                    "content": user_input
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": user_input
                }
            )

            final_text = run_llm_tool_loop(max_steps=5)

            chat_history.append(
                {
                    "role": "assistant",
                    "content": final_text
                }
            )

        return redirect(url_for("index"))

    return render_template("index.html", messages=chat_history)


@app.route("/reset", methods=["POST"])
def reset():
    with conversation_lock:
        reset_messages()

    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        use_reloader=False
    )