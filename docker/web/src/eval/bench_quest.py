"""Banco del motor Quest (sección 5.3): latencia, tamaño de la salida y concurrencia.

Se ejecuta dentro del contenedor web-app y habla con el puente (bridge-api) igual
que lo hace la aplicación, a través de QuestEngine. No usa el modelo de lenguaje.

    docker compose run --rm -v "${PWD}/docker/web/src/eval/resultados:/app/src/eval/resultados" \
        web-app python -m src.eval.bench_quest

Con --mantener N abre N partidas y las deja abiertas 40 s para medir la memoria
del puente desde otra terminal con `docker stats --no-stream`.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import threading
import time

from src.llm_client.catalog import get_game
from src.llm_client.engines.quest_engine import QuestEngine

AQUI = os.path.dirname(os.path.abspath(__file__))
RESULTADOS = os.path.join(AQUI, "resultados")

# Órdenes sin ambigüedad (una orden ambigua abre un menú en el reproductor).
ORDENES = ["look", "inventory", "north", "look", "south", "look", "east", "look", "west", "look"]


def _stats(ms: list[float]) -> dict:
    if not ms:
        return {}
    s = sorted(ms)
    p95 = s[min(len(s) - 1, int(round(0.95 * (len(s) - 1))))]
    return {"n": len(s), "media_ms": round(statistics.mean(s), 1), "p50_ms": round(statistics.median(s), 1),
            "p95_ms": round(p95, 1), "max_ms": round(s[-1], 1)}


def partida(eng: QuestEngine, game, sid: str, ordenes: list[str]) -> dict:
    """Inicia una partida, envía las órdenes y la cierra. Devuelve tiempos y tamaños."""
    t = time.perf_counter()
    r = eng.start_game(sid, game)
    arranque = (time.perf_counter() - t) * 1000
    if not r.ok:
        return {"ok": False, "error": r.error, "arranque_ms": arranque}
    lat, chars, sin_cambio, errores = [], [], 0, 0
    for o in ordenes:
        t = time.perf_counter()
        res = eng.send_command(sid, o)
        lat.append((time.perf_counter() - t) * 1000)
        if not res.ok:
            errores += 1
            continue
        chars.append(len(res.output))
        if not res.changed:   # la página no cambió en 600 ms: la respuesta no llegó a tiempo
            sin_cambio += 1
    eng.close_game(sid)
    return {"ok": True, "arranque_ms": arranque, "lat": lat, "chars": chars,
            "sin_cambio": sin_cambio, "errores": errores}


def latencia(eng: QuestEngine, game, repeticiones: int) -> dict:
    arr, lat, primero, ultimo, sin_cambio, errores = [], [], [], [], 0, 0
    for k in range(repeticiones):
        p = partida(eng, game, f"bq-lat-{k}", ORDENES)
        if not p["ok"]:
            errores += 1
            print(f"  repetición {k + 1}: no se pudo iniciar ({p['error']})")
            continue
        arr.append(p["arranque_ms"])
        lat += p["lat"]
        if p["chars"]:
            primero.append(p["chars"][0])
            ultimo.append(p["chars"][-1])
        sin_cambio += p["sin_cambio"]
        errores += p["errores"]
    return {"arranque": _stats(arr), "orden": _stats(lat),
            "caracteres_primera_orden": round(statistics.mean(primero)) if primero else None,
            "caracteres_ultima_orden": round(statistics.mean(ultimo)) if ultimo else None,
            "ordenes_sin_cambio": sin_cambio, "errores": errores, "ordenes_por_partida": len(ORDENES)}


def concurrencia(eng: QuestEngine, game, niveles=(1, 2, 4)) -> dict:
    res = {}
    for n in niveles:
        resultados = [None] * n

        def jugador(i: int):
            try:
                resultados[i] = partida(eng, game, f"bq-conc-{n}-{i}", ORDENES)
            except Exception as e:   # noqa: BLE001
                resultados[i] = {"ok": False, "error": str(e)}

        t0 = time.perf_counter()
        hilos = [threading.Thread(target=jugador, args=(i,)) for i in range(n)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        dur = time.perf_counter() - t0
        lat = [x for r in resultados if r and r.get("ok") for x in r["lat"]]
        fallidas = sum(1 for r in resultados if not r or not r.get("ok"))
        errores = sum(r.get("errores", 0) for r in resultados if r and r.get("ok"))
        sin_cambio = sum(r.get("sin_cambio", 0) for r in resultados if r and r.get("ok"))
        res[str(n)] = {**_stats(lat), "partidas_fallidas": fallidas, "errores": errores,
                       "ordenes_sin_cambio": sin_cambio, "duracion_s": round(dur, 2)}
    return res


def mantener(eng: QuestEngine, game, n: int, segundos: int = 40) -> None:
    for i in range(n):
        r = eng.start_game(f"bq-mem-{i}", game)
        print(f"  partida {i + 1}: {'abierta' if r.ok else r.error}")
    print(f"\n{n} partidas abiertas durante {segundos} s. Ejecuta ahora en otra terminal:\n"
          "  docker stats --no-stream tfg_text_adventure-bridge-api-1\n")
    time.sleep(segundos)
    for i in range(n):
        eng.close_game(f"bq-mem-{i}")
    print("Partidas cerradas.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--juego", default="quest_tutorial")
    ap.add_argument("--mantener", type=int, help="abre N partidas y las mantiene 40 s (medida de memoria)")
    a = ap.parse_args()

    game = get_game(a.juego)
    if game is None:
        raise SystemExit(f"No encuentro el juego {a.juego!r} en el catálogo")
    eng = QuestEngine()

    if a.mantener:
        mantener(eng, game, a.mantener)
        return

    out = {"entorno": {"python": platform.python_version(), "so": platform.platform(),
                       "puente": eng.bridge, "fecha": time.strftime("%Y-%m-%d %H:%M")}}
    print("Entorno:", out["entorno"])
    out["latencia"] = latencia(eng, game, a.repeticiones)
    print("[latencia]", out["latencia"])
    out["concurrencia"] = concurrencia(eng, game)
    for n, r in out["concurrencia"].items():
        print(f"[concurrencia] {n} partidas: {r}")

    os.makedirs(RESULTADOS, exist_ok=True)
    with open(os.path.join(RESULTADOS, "bench_quest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\nGuardado en", os.path.join(RESULTADOS, "bench_quest.json"))


if __name__ == "__main__":
    main()
