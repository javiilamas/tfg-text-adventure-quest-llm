"""Banco de pruebas del motor Frotz (sin LLM, sin red).

Mide lo que la memoria afirma y hasta ahora no cuantificaba:
  * Latencia de arranque y por comando de FrotzEngine (RNF3, parte del motor).
  * Aislamiento y latencia con N sesiones concurrentes (RF5, RNF2).
  * Memoria residente de cada proceso dfrotz.
  * Seguridad (RNF4): inyeccion de shell, saltos de linea y confinamiento -R.

Uso (dentro del contenedor web, o en Linux con dfrotz instalado):
    python -m src.eval.bench_engine                 # todo
    python -m src.eval.bench_engine --solo latencia
Salida: tabla en consola + src/eval/resultados/bench_engine.json
"""
from __future__ import annotations
import argparse
import json
import os
import platform
import statistics
import tempfile
import threading
import time

from src.llm_client.engines.frotz_engine import FrotzEngine
from src.llm_client.catalog import GameSpec

GAMES_ROOT = os.getenv("GAMES_ROOT", "/app/games")
FROTZ_BIN = os.getenv("FROTZ_BIN", "dfrotz")
OUT_DIR = os.path.join(os.path.dirname(__file__), "resultados")

# Recorridos fijos por juego (comandos validos en cada juego).
RECORRIDOS = {
    "zork1": ["open mailbox", "take leaflet", "read leaflet", "north", "east",
              "open window", "enter", "look", "west", "take lamp", "inventory", "east"],
    "minizork": ["look", "open mailbox", "north", "east", "west", "south", "look"],
    "cave": ["look", "take lantern", "light lantern", "north", "north", "look", "south"],
}


def _game(gid: str) -> GameSpec | None:
    for ext in (".z3", ".z5", ".z8"):
        p = os.path.join(GAMES_ROOT, "zmachine", gid + ext)
        if os.path.exists(p):
            return GameSpec(gid, gid, "frotz", p)
    return None


def _stats(ms: list[float]) -> dict:
    s = sorted(ms)
    p95 = s[max(0, int(round(0.95 * len(s))) - 1)]
    return {"n": len(s), "media_ms": round(statistics.mean(s), 1),
            "p50_ms": round(statistics.median(s), 1), "p95_ms": round(p95, 1),
            "max_ms": round(s[-1], 1)}


def _rss_kb(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except OSError:
        return None
    return None


# ---------------------------------------------------------------- latencia
def latencia(eng: FrotzEngine, repeticiones: int = 5) -> dict:
    res = {}
    for gid, cmds in RECORRIDOS.items():
        g = _game(gid)
        if g is None:
            continue
        arranques, comandos, rss = [], [], []
        for r in range(repeticiones):
            sid = f"lat-{gid}-{r}"
            t = time.perf_counter()
            out = eng.start_game(sid, g)
            arranques.append((time.perf_counter() - t) * 1000)
            assert out.ok, out.error
            for c in cmds:
                t = time.perf_counter()
                eng.send_command(sid, c)
                comandos.append((time.perf_counter() - t) * 1000)
            kb = _rss_kb(eng._get(sid).proc.pid)
            if kb:
                rss.append(kb)
            eng.close_game(sid)
        res[gid] = {"arranque": _stats(arranques), "comando": _stats(comandos),
                    "rss_kb_medio": round(statistics.mean(rss)) if rss else None}
    return res


# ------------------------------------------------------------ concurrencia
def concurrencia(eng: FrotzEngine, niveles=(1, 5, 10, 20), comandos: int = 10) -> dict:
    """N sesiones de minizork a la vez. Las pares van al norte y las impares se
    quedan; al final cada una debe estar donde le toca (aislamiento)."""
    g = _game("minizork")
    if g is None:
        return {}
    res = {}
    for n in niveles:
        lat: list[float] = []
        errores = 0
        lock = threading.Lock()

        def jugador(i: int):
            nonlocal errores
            sid = f"conc-{n}-{i}"
            eng.start_game(sid, g)
            if i % 2 == 0:
                eng.send_command(sid, "north")
            for _ in range(comandos):
                t = time.perf_counter()
                out = eng.send_command(sid, "look").output
                dt = (time.perf_counter() - t) * 1000
                esperado = "North of House" if i % 2 == 0 else "West of House"
                with lock:
                    lat.append(dt)
                    if esperado not in out:
                        errores += 1
            eng.close_game(sid)

        t0 = time.perf_counter()
        hilos = [threading.Thread(target=jugador, args=(i,)) for i in range(n)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        total = time.perf_counter() - t0
        res[str(n)] = {**_stats(lat), "errores_aislamiento": errores,
                       "comandos_totales": n * comandos, "duracion_s": round(total, 2)}
    return res


# --------------------------------------------------------------- seguridad
def seguridad(eng: FrotzEngine) -> dict:
    g = _game("zork1") or _game("minizork")
    if g is None:
        return {}
    tmp = tempfile.mkdtemp(prefix="tfg_seg_")
    canario = os.path.join(tmp, "PWNED")
    sid = "seguridad"
    eng = FrotzEngine(frotz_bin=eng.frotz_bin, save_root=os.path.join(tmp, "saves"))
    eng.start_game(sid, g)
    casos = []

    def caso(nombre: str, cmd: str, comprobar):
        t = time.perf_counter()
        out = eng.send_command(sid, cmd)
        dt = round((time.perf_counter() - t) * 1000)
        vivo = eng._get(sid).proc.poll() is None
        ok = bool(comprobar(out)) and vivo
        casos.append({"caso": nombre, "comando": cmd[:60], "ok": ok,
                      "ms": dt, "salida": out.output[-120:]})

    caso("Inyeccion ';'", f"; touch {canario}", lambda o: not os.path.exists(canario))
    caso("Inyeccion $()", f"$(touch {canario})", lambda o: not os.path.exists(canario))
    caso("Inyeccion backticks", f"`touch {canario}`", lambda o: not os.path.exists(canario))
    caso("Tuberia", "| cat /etc/passwd", lambda o: "root:" not in o.output)
    caso("Salto de linea (look\\nquit)", "look\nquit", lambda o: True)

    # SAVE con ruta que intenta salir del directorio confinado (-R).
    destino = os.path.join(tmp, "escape")
    caso("SAVE: pide nombre de fichero", "save", lambda o: True)
    caso("SAVE con ruta ../ y absoluta", "../../../../.." + destino,
         lambda o: not os.path.exists(destino) and not os.path.exists(destino + ".qzl"))
    # Frotz 2.54 guarda "escape"; Frotz 2.55 añade la extensión: "escape.qzl".
    dir_sesion = os.path.join(tmp, "saves", sid)
    ficheros = sorted(os.listdir(dir_sesion)) if os.path.isdir(dir_sesion) else []
    confinado = any(f in ("escape", "escape.qzl") for f in ficheros)
    casos[-1]["ok"] = casos[-1]["ok"] and confinado
    casos[-1]["ficheros_en_saves"] = ficheros
    caso("SAVE otra vez (mismo nombre)", "save", lambda o: True)
    caso("SAVE: pregunta si sobrescribir", "escape", lambda o: True)
    caso("Confirmar sobrescritura", "y", lambda o: True)
    eng.close_game(sid)
    return {"casos": casos, "dir_saves": eng.save_root, "guardado_dentro_de_saves": confinado}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", choices=["latencia", "concurrencia", "seguridad"])
    ap.add_argument("--repeticiones", type=int, default=5)
    a = ap.parse_args()

    eng = FrotzEngine(frotz_bin=FROTZ_BIN)
    entorno = {"python": platform.python_version(), "so": platform.platform(),
               "cpu": platform.processor() or platform.machine(), "dfrotz": FROTZ_BIN,
               "fecha": time.strftime("%Y-%m-%d %H:%M")}
    out = {"entorno": entorno}
    if a.solo in (None, "latencia"):
        out["latencia"] = latencia(eng, a.repeticiones)
    if a.solo in (None, "concurrencia"):
        out["concurrencia"] = concurrencia(eng)
    if a.solo in (None, "seguridad"):
        out["seguridad"] = seguridad(eng)

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "bench_engine.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("Entorno:", entorno)
    for gid, r in out.get("latencia", {}).items():
        print(f"[latencia] {gid:9s} arranque {r['arranque']}  comando {r['comando']}  RSS {r['rss_kb_medio']} kB")
    for n, r in out.get("concurrencia", {}).items():
        print(f"[concurrencia] {n:>2} sesiones: {r}")
    for c in out.get("seguridad", {}).get("casos", []):
        print(f"[seguridad] {'OK ' if c['ok'] else 'FALLO'} {c['caso']:32s} {c['ms']:>6} ms")


if __name__ == "__main__":
    main()
