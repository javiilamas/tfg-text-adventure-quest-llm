"""FrotzEngine: motor de juegos Z-machine (Zork, etc.) via `dfrotz` (dumb).

Decisiones clave (justificadas en el documento de diseno):
  * Se usa la interfaz "dumb" `dfrotz`, que escribe linea a linea por stdout y
    lee de stdin: NO necesita pseudo-terminal (pty). El `frotz` de curses si lo
    necesitaria, por eso NO se usa.
  * Flags: -m (sin prompts MORE, criticos para no bloquear el lector),
    -p (ASCII plano), -w (ancho fijo), -R <dir> (confina lecturas/escrituras
    de SAVE/RESTORE a un directorio -> seguridad).
  * Cada sesion tiene SU PROPIO proceso (nada de una unica variable global),
    con un hilo lector que vuelca stdout a una cola y un lock por sesion para
    que dos comandos no se entrelacen.
  * Fin de respuesta: lector + cola + idle-timeout + deteccion del prompt ">".
  * Buffering: si existe `stdbuf` se lanza con `stdbuf -o0 -i0` para evitar que
    libc deje la salida atrapada en el buffer del pipe.
Seguridad: el comando SOLO se escribe en el stdin del proceso del juego. No hay
shell (argv como lista, sin shell=True), por lo que es imposible ejecutar
comandos del sistema operativo.
"""
from __future__ import annotations
import os
import time
import queue
import shutil
import threading
import subprocess
from .base import GameEngine, EngineResult


def _looks_like_prompt(text: str, prompt: str) -> bool:
    return text.rstrip().endswith(prompt)


def _clean(text: str, prompt: str = ">") -> str:
    t = text.rstrip()
    if t.endswith(prompt):
        t = t[: -len(prompt)].rstrip()
    return t.strip("\n")


class _FrotzProcess:
    """Envuelve un unico proceso dfrotz y su lectura no bloqueante."""

    def __init__(self, path: str, frotz_bin: str, width: int,
                 save_dir: str | None, use_stdbuf: bool = True):
        argv: list[str] = []
        if use_stdbuf and shutil.which("stdbuf"):
            argv += ["stdbuf", "-o0", "-i0"]
        argv += [frotz_bin, "-m", "-p", "-w", str(width)]
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            argv += ["-R", save_dir]
        argv += [path]

        self.proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self.lock = threading.Lock()
        self._q: "queue.Queue[str | None]" = queue.Queue()
        self.stderr_lines: list[str] = []
        self.alive = True
        self._t_out = threading.Thread(target=self._pump_stdout, daemon=True)
        self._t_err = threading.Thread(target=self._pump_stderr, daemon=True)
        self._t_out.start()
        self._t_err.start()

    def _pump_stdout(self) -> None:
        try:
            while True:
                ch = self.proc.stdout.read(1)
                if ch == "":
                    break
                self._q.put(ch)
        finally:
            self.alive = False
            self._q.put(None)  # centinela EOF

    def _pump_stderr(self) -> None:
        # Drenar stderr SIEMPRE: si no, su buffer de pipe se llena y el hijo se
        # bloquea al escribir.
        try:
            for line in self.proc.stderr:
                self.stderr_lines.append(line)
        except Exception:
            pass

    def read_until_prompt(self, prompt: str = ">", idle: float = 0.12,
                          timeout: float = 12.0) -> str:
        chars: list[str] = []
        start = time.time()
        while True:
            try:
                ch = self._q.get(timeout=idle)
            except queue.Empty:
                # No llegan bytes: si parece prompt o el proceso murio, terminamos.
                if _looks_like_prompt("".join(chars), prompt):
                    break
                if not self.alive and self._q.empty():
                    break
                if time.time() - start > timeout:
                    break
                continue
            if ch is None:  # EOF
                break
            chars.append(ch)
            if time.time() - start > timeout:
                break
        return "".join(chars)

    def send(self, command: str) -> None:
        if self.proc.poll() is not None:
            raise RuntimeError("FROTZ_PROCESS_DEAD")
        self.proc.stdin.write(command.replace("\n", " ").strip() + "\n")
        self.proc.stdin.flush()

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                try:
                    self.proc.stdin.write("quit\n")
                    self.proc.stdin.flush()
                except Exception:
                    pass
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        finally:
            self.alive = False
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass


class FrotzEngine(GameEngine):
    name = "frotz"

    def __init__(self, frotz_bin: str | None = None, width: int | None = None,
                 save_root: str | None = None):
        self.frotz_bin = frotz_bin or os.getenv("FROTZ_BIN", "dfrotz")
        self.width = int(width or os.getenv("FROTZ_WIDTH", "80"))
        self.save_root = save_root or os.getenv("FROTZ_SAVE_DIR", "/tmp/frotz_saves")
        self._procs: dict[str, _FrotzProcess] = {}
        self._reg_lock = threading.Lock()

    def start_game(self, session_id: str, game) -> EngineResult:
        self.close_game(session_id)  # limpia cualquier proceso anterior
        if not os.path.exists(game.path):
            return EngineResult(ok=False, error=f"GAME_FILE_NOT_FOUND: {game.path}")
        save_dir = os.path.join(self.save_root, _safe(session_id))
        try:
            p = _FrotzProcess(game.path, self.frotz_bin, self.width, save_dir)
        except FileNotFoundError:
            return EngineResult(ok=False, error=f"FROTZ_BIN_NOT_FOUND: {self.frotz_bin}")
        with self._reg_lock:
            self._procs[session_id] = p
        with p.lock:
            banner = p.read_until_prompt()
        if p.proc.poll() is not None and not banner.strip():
            err = "".join(p.stderr_lines)[:500]
            return EngineResult(ok=False, error=f"FROTZ_FAILED_TO_START: {err}")
        return EngineResult(ok=True, output=_clean(banner))

    def send_command(self, session_id: str, command: str) -> EngineResult:
        p = self._get(session_id)
        if p is None:
            return EngineResult(ok=False, error="NO_ACTIVE_FROTZ_SESSION")
        with p.lock:
            try:
                p.send(command)
            except Exception as e:
                return EngineResult(ok=False, error=str(e))
            out = p.read_until_prompt()
        return EngineResult(ok=True, output=_clean(out))

    def move(self, session_id: str, direction: str) -> EngineResult:
        # Dialecto Z-machine: la direccion sola ("east"), no "go east".
        return self.send_command(session_id, direction)

    def close_game(self, session_id: str) -> None:
        with self._reg_lock:
            p = self._procs.pop(session_id, None)
        if p is not None:
            p.close()

    def _get(self, session_id: str) -> _FrotzProcess | None:
        with self._reg_lock:
            return self._procs.get(session_id)


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name) or "default"
