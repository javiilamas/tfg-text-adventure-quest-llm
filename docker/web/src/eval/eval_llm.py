"""Evaluacion de extremo a extremo con el LLM REAL (OpenRouter).

Ejecuta la bateria de casos de casos_llm.json a traves del MISMO bucle que usa
la web (run_llm_tool_loop de app.py) y mide, para cada caso y repeticion:
  * exito segun comprobaciones automaticas sobre el estado REAL del motor;
  * latencia del turno, numero de llamadas al LLM y de tools;
  * tokens de entrada/salida y coste estimado.
Tambien hay un modo "partida larga" que mide como crece el contexto por turno.

Uso (dentro del contenedor web, con OPENROUTER_API_KEY definida):
    python -m src.eval.eval_llm --repeticiones 3
    python -m src.eval.eval_llm --partida-larga
    python -m src.eval.eval_llm --simulado        # sin red: solo prueba el arnes
Resultados en src/eval/resultados/: CSV por ejecucion, resumen.md con tablas
listas para la memoria y revision_manual.md con las narraciones a revisar.

Precio por defecto: openai/gpt-4o-mini (0,15 $/M entrada, 0,60 $/M salida).
Compruebalo en https://openrouter.ai/openai/gpt-4o-mini y ajusta --precio-*.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import re
import statistics
import time

from src.web_app import app as webapp
from src.llm_client.sessions import MANAGER
from src.llm_client.mcp_client import call_tool as _real_call_tool

AQUI = os.path.dirname(__file__)
OUT_DIR = os.path.join(AQUI, "resultados")


# ------------------------------------------------------------- instrumentos
class Traza:
    """Envuelve call_llm y call_tool para registrar lo que pasa en un turno."""

    def __init__(self, llm_fn):
        self.llm_fn = llm_fn
        self.reset()

    def reset(self):
        self.llamadas_llm = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.tools: list[dict] = []

    def llm(self, messages):
        self.llamadas_llm += 1
        r = self.llm_fn(messages)
        u = (r or {}).get("usage") or {}
        self.tokens_in += int(u.get("prompt_tokens") or 0)
        self.tokens_out += int(u.get("completion_tokens") or 0)
        return r

    def tool(self, name, args, session_id="web"):
        res = _real_call_tool(name, args, session_id=session_id)
        self.tools.append({"name": name, "args": args, "ok": res.get("ok", True),
                           "error": res.get("error")})
        return res

    def comandos(self) -> list[str]:
        """Comandos de juego efectivamente enviados al motor."""
        out = []
        for t in self.tools:
            if t["name"] == "send_game_command":
                out.append(str(t["args"].get("command", "")).strip().lower())
            elif t["name"] == "move":
                out.append(str(t["args"].get("direction", "")).lower())
            elif t["name"] == "look":
                out.append("look")
        return out


def _inyectar_tool(st, sid, name, args, n):
    """Ejecuta una tool y la deja en el historial como si la hubiera pedido el
    modelo, para que el contexto del LLM sea coherente con el estado del motor."""
    cid = f"prep_{n}"
    res = _real_call_tool(name, args, session_id=sid)
    st["messages"].append({"role": "assistant", "content": None, "tool_calls": [
        {"id": cid, "type": "function",
         "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}]})
    st["messages"].append({"role": "tool", "tool_call_id": cid,
                           "content": json.dumps(res, ensure_ascii=False)})
    return res


def preparar(sid, caso):
    webapp._STATE.pop(sid, None)
    MANAGER.close(sid)
    st = webapp._state(sid)
    if caso.get("juego"):
        st["messages"].append({"role": "user", "content": f"Quiero jugar a {caso['juego']}"})
        r = _inyectar_tool(st, sid, "start_game", {"game_id": caso["juego"]}, 0)
        if not r.get("ok"):
            raise RuntimeError(f"No se pudo iniciar {caso['juego']}: {r}")
        for i, c in enumerate(caso.get("preparacion", []), 1):
            _inyectar_tool(st, sid, "send_game_command", {"command": c}, i)
        st["messages"].append({"role": "assistant", "content": "De acuerdo, la partida está en marcha."})
    return st


def comprobar(sid, caso, traza, respuesta) -> list[str]:
    """Devuelve la lista de comprobaciones fallidas (vacia = exito)."""
    fallos = []
    nombres = [t["name"] for t in traza.tools]
    for t in caso.get("tools_esperadas", []):
        if t not in nombres:
            fallos.append(f"falta tool {t}")
    for t in caso.get("tools_prohibidas", []):
        if t in nombres:
            fallos.append(f"tool prohibida {t}")
    if caso.get("comando_regex"):
        rx = re.compile(caso["comando_regex"], re.I)
        if not any(rx.search(c) for c in traza.comandos()):
            fallos.append(f"ningun comando casa /{caso['comando_regex']}/ ({traza.comandos()})")
    if caso.get("juego_activo"):
        cur = MANAGER.current(sid) or {}
        if cur.get("game_id") != caso["juego_activo"]:
            fallos.append(f"juego activo {cur.get('game_id')} != {caso['juego_activo']}")
    for chk in caso.get("estado", []):
        out = MANAGER.send_command(sid, chk["cmd"]).output
        if "contiene" in chk and chk["contiene"].lower() not in out.lower():
            fallos.append(f"'{chk['cmd']}' no contiene '{chk['contiene']}'")
        if "no_contiene" in chk and chk["no_contiene"].lower() in out.lower():
            fallos.append(f"'{chk['cmd']}' contiene '{chk['no_contiene']}'")
    if caso.get("respuesta_no_regex") and re.search(caso["respuesta_no_regex"], respuesta or "", re.I):
        fallos.append("la narracion afirma algo prohibido")
    if caso.get("canario") and os.path.exists(caso["canario"]):
        fallos.append("canario creado: posible ejecucion de comandos")
    return fallos


def ejecutar_caso(caso, rep, traza) -> dict:
    sid = f"eval-{caso['id']}-{rep}"
    if caso.get("canario") and os.path.exists(caso["canario"]):
        os.remove(caso["canario"])
    st = preparar(sid, caso)
    traza.reset()
    t0 = time.perf_counter()
    respuesta = ""
    for turno in caso["turnos"]:
        st["messages"].append({"role": "user", "content": turno})
        respuesta = webapp.run_llm_tool_loop(sid)
    lat = time.perf_counter() - t0
    fallos = comprobar(sid, caso, traza, respuesta)
    MANAGER.close(sid)
    return {"id": caso["id"], "categoria": caso["categoria"], "rep": rep,
            "exito": not fallos, "fallos": "; ".join(fallos),
            "latencia_s": round(lat, 2), "turnos": len(caso["turnos"]),
            "llamadas_llm": traza.llamadas_llm, "tools": len(traza.tools),
            "tokens_in": traza.tokens_in, "tokens_out": traza.tokens_out,
            "comandos": " | ".join(traza.comandos()),
            "tools_usadas": " ".join(t["name"] for t in traza.tools),
            "revision_manual": bool(caso.get("revision_manual")),
            "respuesta": (respuesta or "").replace("\n", " ")}


# ------------------------------------------------------------- resumen
def _p95(v):
    s = sorted(v)
    return s[max(0, int(round(0.95 * len(s))) - 1)] if s else 0


def resumen(filas, precio_in, precio_out, modelo) -> str:
    def coste(f):
        return (f["tokens_in"] * precio_in + f["tokens_out"] * precio_out) / 1e6

    lineas = [f"# Resultados eval_llm ({modelo}, {time.strftime('%Y-%m-%d %H:%M')})", "",
              "| Categoría | Casos | Ejecuciones | Éxito | Latencia media (s) | p95 (s) | Llamadas LLM/turno | Tokens entrada/turno | Coste/turno (USD) |",
              "|---|---|---|---|---|---|---|---|---|"]
    cats = sorted({f["categoria"] for f in filas}) + ["TOTAL"]
    for c in cats:
        fs = filas if c == "TOTAL" else [f for f in filas if f["categoria"] == c]
        if not fs:
            continue
        turnos = sum(f["turnos"] for f in fs)
        lat_turno = [f["latencia_s"] / f["turnos"] for f in fs]
        lineas.append("| {} | {} | {} | {:.0%} | {:.2f} | {:.2f} | {:.2f} | {:.0f} | {:.5f} |".format(
            c, len({f['id'] for f in fs}), len(fs), sum(f["exito"] for f in fs) / len(fs),
            statistics.mean(lat_turno), _p95(lat_turno),
            sum(f["llamadas_llm"] for f in fs) / turnos,
            sum(f["tokens_in"] for f in fs) / turnos,
            sum(coste(f) for f in fs) / turnos))
    lineas += ["", "## Casos con algún fallo", ""]
    for f in filas:
        if not f["exito"]:
            lineas.append(f"- **{f['id']}** (rep {f['rep']}): {f['fallos']}")
    return "\n".join(lineas) + "\n"


# ------------------------------------------------------------- modo simulado
_REGLAS = [(r"juegos", ("list_games", {})), (r"zork", ("start_game", {"game_id": "zork1"})),
           (r"cueva", ("start_game", {"game_id": "cave"})), (r"minizork", ("start_game", {"game_id": "minizork"})),
           (r"buz", ("send_game_command", {"command": "open mailbox"})),
           (r"folleto", ("send_game_command", {"command": "take leaflet"})),
           (r"norte", ("move", {"direction": "north"})), (r"llevo", ("send_game_command", {"command": "inventory"}))]


def llm_simulado(messages):
    """Modelo de juguete por reglas: solo sirve para probar el arnes sin red."""
    last = messages[-1]
    usage = {"prompt_tokens": sum(len(str(m.get("content") or "")) for m in messages) // 4,
             "completion_tokens": 20}
    if last.get("role") == "user":
        for rx, (name, args) in _REGLAS:
            if re.search(rx, last["content"], re.I):
                return {"usage": usage, "choices": [{"message": {"role": "assistant", "content": None,
                        "tool_calls": [{"id": f"sim{time.time_ns()}", "type": "function",
                                        "function": {"name": name, "arguments": json.dumps(args)}}]}}]}
        return {"usage": usage, "choices": [{"message": {"role": "assistant", "content": "No sé hacer eso."}}]}
    return {"usage": usage, "choices": [{"message": {"role": "assistant",
            "content": "(simulado) " + str(last.get("content", ""))[:120]}}]}


# ------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--casos", default=os.path.join(AQUI, "casos_llm.json"))
    ap.add_argument("--repeticiones", type=int, default=3)
    ap.add_argument("--solo", help="ids separados por comas, p.ej. C01,A02")
    ap.add_argument("--partida-larga", action="store_true")
    ap.add_argument("--simulado", action="store_true")
    ap.add_argument("--precio-entrada", type=float, default=0.15, help="USD por millon de tokens")
    ap.add_argument("--precio-salida", type=float, default=0.60, help="USD por millon de tokens")
    a = ap.parse_args()

    with open(a.casos, encoding="utf-8") as f:
        data = json.load(f)
    from src.llm_client.config import MODEL
    modelo = "SIMULADO" if a.simulado else MODEL
    traza = Traza(llm_simulado if a.simulado else webapp.call_llm)
    webapp.call_llm = traza.llm      # el bucle de la web usara los instrumentos
    webapp.call_tool = traza.tool
    os.makedirs(OUT_DIR, exist_ok=True)
    marca = time.strftime("%Y%m%d_%H%M")

    if a.partida_larga:
        pl = data["partida_larga"]
        caso = {"id": "PL", "categoria": "partida_larga", "juego": pl["juego"], "turnos": []}
        sid = "eval-partida-larga"
        st = preparar(sid, caso)
        filas = []
        for i, turno in enumerate(pl["turnos"], 1):
            traza.reset()
            st["messages"].append({"role": "user", "content": turno})
            t0 = time.perf_counter()
            resp = webapp.run_llm_tool_loop(sid)
            filas.append({"turno": i, "mensaje": turno, "latencia_s": round(time.perf_counter() - t0, 2),
                          "llamadas_llm": traza.llamadas_llm, "tokens_in": traza.tokens_in,
                          "tokens_out": traza.tokens_out, "mensajes_historial": len(st["messages"]),
                          "comandos": " | ".join(traza.comandos()), "respuesta": resp.replace("\n", " ")})
            print(f"turno {i:2d}: {filas[-1]['latencia_s']:5.2f}s  in={traza.tokens_in:6d}  {turno}")
        ruta = os.path.join(OUT_DIR, f"partida_larga_{marca}.csv")
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            w.writeheader()
            w.writerows(filas)
        print("Guardado:", ruta)
        return

    casos = data["casos"]
    if a.solo:
        ids = set(a.solo.split(","))
        casos = [c for c in casos if c["id"] in ids]
    filas = []
    for caso in casos:
        for rep in range(1, a.repeticiones + 1):
            try:
                fila = ejecutar_caso(caso, rep, traza)
            except Exception as e:  # un caso roto no debe parar la bateria
                fila = {"id": caso["id"], "categoria": caso["categoria"], "rep": rep, "exito": False,
                        "fallos": f"EXCEPCION: {e}", "latencia_s": 0, "turnos": len(caso["turnos"]),
                        "llamadas_llm": 0, "tools": 0, "tokens_in": 0, "tokens_out": 0, "comandos": "",
                        "tools_usadas": "", "revision_manual": False, "respuesta": ""}
            filas.append(fila)
            print(f"{fila['id']} rep{rep}: {'OK ' if fila['exito'] else 'FALLO'} "
                  f"{fila['latencia_s']:5.2f}s  llm={fila['llamadas_llm']} tools={fila['tools_usadas']}  {fila['fallos']}")

    base = os.path.join(OUT_DIR, f"llm_{marca}{'_simulado' if a.simulado else ''}")
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
    with open(base + "_resumen.md", "w", encoding="utf-8") as f:
        f.write(resumen(filas, a.precio_entrada, a.precio_salida, modelo))
    with open(base + "_revision_manual.md", "w", encoding="utf-8") as f:
        f.write("# Narraciones a revisar a mano\n\nMarca cada una como CORRECTA (no afirma nada "
                "que el motor no haya dicho) o INCORRECTA.\n\n")
        for fila in filas:
            if fila["revision_manual"]:
                f.write(f"## {fila['id']} rep {fila['rep']}\n- Comandos: {fila['comandos']}\n"
                        f"- Narración: {fila['respuesta']}\n- Valoración: \n\n")
    print("\n" + resumen(filas, a.precio_entrada, a.precio_salida, modelo))
    print("Guardado:", base + ".csv")


if __name__ == "__main__":
    main()
