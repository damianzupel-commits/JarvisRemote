"""Tool de generación de imágenes (`generate_image`) vía ComfyUI + Flux.1 Schnell,
corriendo localmente en la GPU (misma instalación de E:\\ComfyUI que `generate_video`).

Flux.1 Schnell (GGUF Q4_K_S, ~6.8GB) se eligió por: licencia Apache-2.0 (a diferencia
de Flux.1 Dev, que es solo para uso no comercial), destilado a 4 pasos sin CFG real
(genera rápido, workflow de una sola pasada de KSampler, más simple que el de Wan
2.2 que necesita dos expertos), mejor adherencia al prompt que SDXL en la mayoría de
comparaciones, y reusa el mismo custom node UnetLoaderGGUF ya instalado para Wan --
en Q4_K_S entra en los 12GB de VRAM de la RX 6700 XT junto con los text encoders
(t5xxl en fp8, clip_l) usando el mismo offloading parcial que ya vimos funcionar con
Wan cuando no entra completo.

Mismo patrón de coordinación de VRAM y ciclo de vida de ComfyUI que `generate_video`
(ver app/tools/_comfyui_shared.py): antes de generar se descarga de VRAM cualquier
modelo de Ollama cargado y se lo recarga al terminar; si ComfyUI no está corriendo se
lo arranca y se lo cierra al terminar (solo si fue esta tool la que lo arrancó).
"""

import random
import subprocess

import httpx

from . import register_tool
from ._comfyui_shared import (
    comfyui_is_up,
    comfyui_output_dir,
    extract_output_file,
    list_loaded_ollama_models,
    queue_prompt,
    reload_ollama_model,
    start_comfyui_process,
    stop_comfyui_process,
    unload_ollama_model,
    wait_comfyui_ready,
    wait_for_result,
)
from ..config import settings


def _round_to_16(value: int) -> int:
    return max(256, min(1536, round(value / 16) * 16))


def _build_workflow(prompt: str, width: int, height: int, seed: int) -> dict:
    w = _round_to_16(width)
    h = _round_to_16(height)
    return {
        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "flux1-schnell-Q4_K_S.gguf"},
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                "clip_name2": "clip_l.safetensors",
                "type": "flux",
            },
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": w, "height": h, "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": f"jarvis_img_{seed}"},
        },
    }


@register_tool(
    name="generate_image",
    description=(
        "Genera una imagen a partir de una descripción de texto, usando Flux.1 Schnell corriendo "
        "localmente en la GPU vía ComfyUI. Usa toda la VRAM disponible: antes de generar se descarga "
        "de VRAM el modelo de texto de Ollama (se recarga solo al terminar), así que otras tools que "
        "dependan del modelo de texto van a esperar hasta que esto termine. Describí la escena en "
        "inglés (Flux entiende mejor prompts en inglés) y de forma simple y concreta."
    ),
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descripción en inglés de la imagen a generar (ej. 'a red apple on a wooden table, simple clean background').",
            },
            "width": {"type": "integer", "description": "Ancho en píxeles, múltiplo de 16 (default 512)."},
            "height": {"type": "integer", "description": "Alto en píxeles, múltiplo de 16 (default 512)."},
        },
        "required": ["prompt"],
    },
)
async def generate_image(prompt: str, width: int = 512, height: int = 512) -> dict:
    async with httpx.AsyncClient() as client:
        unloaded_models = await list_loaded_ollama_models(client)
        for name in unloaded_models:
            await unload_ollama_model(client, name)

        started_comfyui = False
        proc: subprocess.Popen | None = None
        try:
            if not await comfyui_is_up(client):
                proc = start_comfyui_process()
                started_comfyui = True
                await wait_comfyui_ready(client, timeout=settings.comfyui_startup_timeout)

            seed = random.randint(0, 2**32 - 1)
            workflow = _build_workflow(prompt, width, height, seed)
            prompt_id = await queue_prompt(client, workflow)

            # Flux Schnell (4 pasos, una sola pasada) es bastante más rápido que el
            # workflow de dos expertos de Wan, pero se deja el mismo margen generoso
            # que en generate_video dado lo variable que resultó el tiempo real
            # (presión de RAM/swapping observada en esta máquina).
            generation_timeout = settings.comfyui_generation_timeout_image
            history_entry = await wait_for_result(client, prompt_id, timeout=generation_timeout)
            output_file = extract_output_file(history_entry)

            subfolder = output_file.get("subfolder", "")
            output_dir = comfyui_output_dir()
            path = (output_dir / subfolder / output_file["filename"]) if subfolder else (output_dir / output_file["filename"])

            return {
                "path": str(path),
                "filename": output_file["filename"],
                "width": _round_to_16(width),
                "height": _round_to_16(height),
                "prompt": prompt,
            }
        finally:
            if started_comfyui and proc is not None:
                stop_comfyui_process(proc)
            for name in unloaded_models:
                await reload_ollama_model(client, name)
