"""Infraestructura común para tools que usan ComfyUI (generate_video, generate_image):
arranque/parada del server, coordinación de VRAM con Ollama, y el ciclo
encolar-esperar-extraer resultado. No es una tool en sí misma -- no se registra
nada acá, solo funciones que las tools importan.
"""

import asyncio
import subprocess
import time
from pathlib import Path

import httpx

from ..config import settings


def comfyui_output_dir() -> Path:
    return Path(settings.comfyui_dir) / "ComfyUI" / "output"


async def comfyui_is_up(client: httpx.AsyncClient) -> bool:
    try:
        resp = await client.get(f"{settings.comfyui_base_url}/system_stats", timeout=5)
        return resp.status_code == 200
    except httpx.HTTPError:
        return False


async def list_loaded_ollama_models(client: httpx.AsyncClient) -> list[str]:
    try:
        resp = await client.get(f"{settings.ollama_native_base_url}/api/ps", timeout=10)
        resp.raise_for_status()
    except httpx.HTTPError:
        # Si Ollama no está corriendo, no hay nada que descargar de VRAM.
        return []
    return [m["name"] for m in resp.json().get("models", [])]


async def unload_ollama_model(client: httpx.AsyncClient, name: str) -> None:
    try:
        await client.post(
            f"{settings.ollama_native_base_url}/api/generate",
            json={"model": name, "keep_alive": 0},
            timeout=30,
        )
    except httpx.HTTPError:
        pass


async def reload_ollama_model(client: httpx.AsyncClient, name: str) -> None:
    try:
        await client.post(
            f"{settings.ollama_native_base_url}/api/generate",
            json={"model": name, "prompt": "", "keep_alive": "5m"},
            timeout=120,
        )
    except httpx.HTTPError:
        pass


def comfyui_log_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "comfyui.log"


def _kill_stale_comfyui_processes() -> None:
    """Mata cualquier proceso de ComfyUI que haya quedado vivo pero sin
    responder por HTTP -- pasa en la práctica cuando el proceso crashea a
    nivel nativo (visto con gfx1031, no soportado oficialmente por ROCm: el
    proceso queda colgado en vez de terminar limpio) y la corrida siguiente
    fallaba con 'Could not acquire lock on database comfyui.db: Another
    ComfyUI process may already be using it', porque el proceso zombie seguía
    reteniendo el lock de SQLite pese a no responder más. `comfyui_is_up()`
    solo confirma que el HTTP no contesta, no que el proceso realmente murió.
    """
    comfyui_main = str(Path(settings.comfyui_dir) / "ComfyUI" / "main.py")
    try:
        output = subprocess.check_output(
            [
                "wmic", "process", "where",
                f"CommandLine like '%{comfyui_main.replace(chr(92), chr(92) * 2)}%'",
                "get", "ProcessId",
            ],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        return
    for line in output.splitlines():
        line = line.strip()
        if line.isdigit():
            subprocess.run(
                ["taskkill", "/PID", line, "/T", "/F"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                capture_output=True,
            )


def start_comfyui_process() -> subprocess.Popen:
    _kill_stale_comfyui_processes()
    comfyui_python = Path(settings.comfyui_python_path)
    comfyui_main = Path(settings.comfyui_dir) / "ComfyUI" / "main.py"
    # stdout/stderr a un log file en vez de DEVNULL -- sin esto, un crash de
    # ComfyUI (esperable: gfx1031 no está oficialmente soportado por ROCm, ver
    # el comentario de COMFYUI_PYTHON_PATH en config.py) no dejaba ningún rastro
    # de la causa real, solo el colgado del polling en el lado del backend.
    log_file = open(comfyui_log_path(), "a", encoding="utf-8")
    return subprocess.Popen(
        [str(comfyui_python), "-s", str(comfyui_main), "--windows-standalone-build"],
        cwd=str(Path(settings.comfyui_dir)),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )


def stop_comfyui_process(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=15)


async def wait_comfyui_ready(client: httpx.AsyncClient, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await comfyui_is_up(client):
            return
        await asyncio.sleep(2)
    raise TimeoutError(f"ComfyUI no respondió en {settings.comfyui_base_url} tras {timeout}s de iniciado")


async def queue_prompt(client: httpx.AsyncClient, workflow: dict) -> str:
    resp = await client.post(f"{settings.comfyui_base_url}/prompt", json={"prompt": workflow}, timeout=30)
    resp.raise_for_status()
    return resp.json()["prompt_id"]


async def wait_for_result(client: httpx.AsyncClient, prompt_id: str, timeout: float) -> dict:
    # Si ComfyUI crashea a mitad de una generación (visto en la práctica con
    # gfx1031, no soportado oficialmente por ROCm -- dos generaciones seguidas
    # alcanzan para tirar el proceso sin ningún traceback), el poll siguiente
    # falla por conexión en vez de devolver un resultado. Antes esto no se
    # distinguía de "sigue corriendo, todavía no terminó" y el chat se quedaba
    # colgado hasta el timeout completo (600s default) esperando una respuesta
    # que ya no iba a llegar. Tres fallas de conexión seguidas (no una sola,
    # que podría ser un blip de red transitorio) se toman como "ComfyUI se
    # cayó" y cortan la espera en ~15s en vez de en 10 minutos.
    deadline = time.monotonic() + timeout
    consecutive_connection_errors = 0
    while time.monotonic() < deadline:
        try:
            resp = await client.get(f"{settings.comfyui_base_url}/history/{prompt_id}", timeout=10)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ReadError, httpx.ReadTimeout) as exc:
            consecutive_connection_errors += 1
            if consecutive_connection_errors >= 3:
                raise RuntimeError(
                    f"ComfyUI dejó de responder durante la generación (prompt_id={prompt_id}) "
                    f"-- probablemente crasheó. Revisá backend/comfyui.log."
                ) from exc
            await asyncio.sleep(5)
            continue
        consecutive_connection_errors = 0
        data = resp.json()
        if prompt_id in data:
            return data[prompt_id]
        await asyncio.sleep(5)
    raise TimeoutError(f"ComfyUI no terminó en {timeout}s (prompt_id={prompt_id})")


def extract_output_file(history_entry: dict) -> dict:
    for node_output in history_entry.get("outputs", {}).values():
        for key in ("images", "gifs", "videos"):
            files = node_output.get(key)
            if files:
                return files[0]
    raise RuntimeError(f"ComfyUI no devolvió ningún archivo de salida: {history_entry}")
