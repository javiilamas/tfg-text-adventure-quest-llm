import os
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from playwright.async_api import Page, async_playwright


app = FastAPI()

WEBPLAYER_URL = os.getenv("WEBPLAYER_URL", "http://localhost:8080")

SESSIONS: Dict[str, Dict[str, Any]] = {}
LOCKS: Dict[str, asyncio.Lock] = {}


class NewSessionRequest(BaseModel):
    sessionId: str
    questFilePath: str


class CommandRequest(BaseModel):
    sessionId: str
    text: str


def _lock(session_id: str) -> asyncio.Lock:
    if session_id not in LOCKS:
        LOCKS[session_id] = asyncio.Lock()
    return LOCKS[session_id]


async def _get_text_area(page: Page) -> str:
    """
    Devuelve todo el texto visible del WebPlayer.
    Más adelante se puede refinar para devolver solo la última respuesta.
    """
    return await page.inner_text("body")


async def _find_command_input(page: Page):
    """
    Busca el input donde se escriben comandos en el WebPlayer.
    Normalmente es el último input visible.
    """
    inputs = page.locator("input:visible")
    count = await inputs.count()

    if count == 0:
        raise RuntimeError("No encuentro ningún input visible para escribir comandos.")

    return inputs.nth(count - 1)


@app.get("/health")
async def health():
    return {
        "ok": True,
        "webplayer": WEBPLAYER_URL,
        "sessions": list(SESSIONS.keys())
    }


@app.post("/session/new")
async def session_new(body: NewSessionRequest):
    if body.sessionId in SESSIONS:
        return {
            "ok": True,
            "sessionId": body.sessionId,
            "message": "Session already exists"
        }

    p = await async_playwright().start()
    browser = None
    context = None

    try:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(WEBPLAYER_URL, wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Intento 1: cargar directamente mediante input[type=file].
        # Esta es la forma más robusta si el input existe en el DOM.
        file_input = page.locator('input[type="file"]')

        if await file_input.count() > 0:
            await file_input.first.set_input_files(body.questFilePath)

        else:
            # Intento 2: buscar botón/enlace visible para abrir selector de archivos.
            # No usamos "Browse" porque en Quest Viva aparece en un texto oculto/fallback.
            candidates = [
                "Open a file",
                "Open file",
                "Choose file"
            ]

            loaded = False

            for text in candidates:
                locator = page.get_by_text(text, exact=False)
                count = await locator.count()

                for i in range(count):
                    candidate = locator.nth(i)

                    if await candidate.is_visible():
                        async with page.expect_file_chooser() as fc_info:
                            await candidate.click()

                        chooser = await fc_info.value
                        await chooser.set_files(body.questFilePath)
                        loaded = True
                        break

                if loaded:
                    break

            if not loaded:
                body_text = await page.inner_text("body")
                raise RuntimeError(
                    "No encontré input[type=file] ni botón visible para cargar archivo. "
                    f"Texto visible en página: {body_text[:1000]}"
                )

        # Damos tiempo a que Quest cargue el juego.
        await page.wait_for_timeout(2500)

        SESSIONS[body.sessionId] = {
            "playwright": p,
            "browser": browser,
            "context": context,
            "page": page,
        }

        return {
            "ok": True,
            "sessionId": body.sessionId,
            "message": "Quest loaded in WebPlayer"
        }

    except Exception as e:
        if context is not None:
            await context.close()
        if browser is not None:
            await browser.close()
        await p.stop()

        raise HTTPException(
            status_code=500,
            detail=f"No pude cargar el .quest: {e}"
        )


@app.post("/session/command")
async def session_command(body: CommandRequest):
    if body.sessionId not in SESSIONS:
        raise HTTPException(status_code=404, detail="SESSION_NOT_FOUND")

    async with _lock(body.sessionId):
        page: Page = SESSIONS[body.sessionId]["page"]

        before = await _get_text_area(page)

        cmd_input = await _find_command_input(page)
        await cmd_input.click()
        await cmd_input.fill(body.text)
        await cmd_input.press("Enter")

        # Espera provisional. Más adelante puede sustituirse por estabilización del DOM.
        await page.wait_for_timeout(600)

        after = await _get_text_area(page)

        return {
            "ok": True,
            "output": after,
            "changed": after != before
        }


@app.post("/session/close")
async def session_close(sessionId: str):
    if sessionId not in SESSIONS:
        return {"ok": True}

    s = SESSIONS.pop(sessionId)

    await s["context"].close()
    await s["browser"].close()
    await s["playwright"].stop()

    if sessionId in LOCKS:
        LOCKS.pop(sessionId)

    return {
        "ok": True,
        "message": "Closed"
    }