"""Tool de generación de video (`generate_video`) vía ComfyUI + Wan 2.2, corriendo
localmente en la GPU (ver E:\\ComfyUI, mismo workflow que la prueba de la manzana
rotando).

ComfyUI y el modelo de texto de Ollama compiten por la misma VRAM (12GB en la RX
6700 XT) -- antes de generar, se descarga de VRAM cualquier modelo de Ollama
cargado (vía su API nativa, `/api/generate` con `keep_alive: 0`) y se lo vuelve a
cargar al terminar, mismo patrón ya usado con LM Studio. Si ComfyUI no está
corriendo, se lo arranca como subproceso y se lo cierra al terminar (solo si fue
este tool el que lo arrancó -- si ya estaba corriendo de antes, se lo deja como
estaba).
"""

import random
import subprocess

import httpx

from ..config import settings
from . import register_tool
from ._comfyui_shared import (
    comfyui_is_up as _comfyui_is_up,
    comfyui_output_dir as _comfyui_output_dir,
    extract_output_file as _extract_output_file,
    list_loaded_ollama_models as _list_loaded_ollama_models,
    queue_prompt as _queue_prompt,
    reload_ollama_model as _reload_ollama_model,
    start_comfyui_process as _start_comfyui_process,
    stop_comfyui_process as _stop_comfyui_process,
    unload_ollama_model as _unload_ollama_model,
    wait_comfyui_ready as _wait_comfyui_ready,
    wait_for_result as _wait_for_result,
)

_FPS = 16


def _build_workflow(prompt: str, duration_seconds: float, seed: int) -> dict:
    # Wan necesita un largo de latente de la forma 4k+1 frames.
    raw_length = round(_FPS * duration_seconds)
    length = max(5, (raw_length // 4) * 4 + 1)
    return {
        "1": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"},
        },
        "2": {"class_type": "VAELoader", "inputs": {"vae_name": "Wan2.1_VAE.safetensors"}},
        "3": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "Wan2.2-T2V-A14B-HighNoise-Q4_K_M.gguf"},
        },
        "4": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {"unet_name": "Wan2.2-T2V-A14B-LowNoise-Q4_K_M.gguf"},
        },
        "5": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["3", 0],
                "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_high_noise.safetensors",
                "strength_model": 1.0,
            },
        },
        "6": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["4", 0],
                "lora_name": "wan2.2_t2v_lightx2v_4steps_lora_v1.1_low_noise.safetensors",
                "strength_model": 1.0,
            },
        },
        "7": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["5", 0], "shift": 5.0}},
        "8": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["6", 0], "shift": 5.0}},
        "9": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 0], "text": prompt}},
        "10": {
            "class_type": "CLIPTextEncode",
            "inputs": {"clip": ["1", 0], "text": "blurry, low quality, static, distorted"},
        },
        "11": {
            "class_type": "EmptyHunyuanLatentVideo",
            "inputs": {"width": 480, "height": 480, "length": length, "batch_size": 1},
        },
        "12": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["7", 0],
                "positive": ["9", 0],
                "negative": ["10", 0],
                "latent_image": ["11", 0],
                "add_noise": "enable",
                "noise_seed": seed,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 0,
                "end_at_step": 2,
                "return_with_leftover_noise": "enable",
            },
        },
        "13": {
            "class_type": "KSamplerAdvanced",
            "inputs": {
                "model": ["8", 0],
                "positive": ["9", 0],
                "negative": ["10", 0],
                "latent_image": ["12", 0],
                "add_noise": "disable",
                "noise_seed": 0,
                "steps": 4,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "start_at_step": 2,
                "end_at_step": 4,
                "return_with_leftover_noise": "disable",
            },
        },
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["2", 0]}},
        "15": {"class_type": "CreateVideo", "inputs": {"images": ["14", 0], "fps": _FPS}},
        "16": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["15", 0],
                "filename_prefix": f"jarvis_gen_{seed}",
                "format": "auto",
                "codec": "auto",
            },
        },
    }


@register_tool(
    name="generate_video",
    description=(
        "Genera un video corto (1 a 5 segundos) a partir de una descripción de texto, usando Wan 2.2 "
        "corriendo localmente en la GPU vía ComfyUI. Es lento (puede tardar varios minutos, más cuanto "
        "más largo el video) y usa toda la VRAM disponible: antes de generar se descarga de VRAM el "
        "modelo de texto de Ollama (se recarga solo al terminar), así que otras tools que dependan del "
        "modelo de texto van a esperar hasta que esto termine. Describí la escena en inglés (los "
        "modelos Wan entienden mejor prompts en inglés) y de forma simple y concreta."
    ),
    parameters={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Descripción en inglés de la escena a generar (ej. 'a red apple slowly rotating on a wooden table').",
            },
            "duration_seconds": {
                "type": "number",
                "description": "Duración aproximada del clip en segundos, entre 1 y 5. Default 1.",
            },
        },
        "required": ["prompt"],
    },
)
async def generate_video(prompt: str, duration_seconds: float = 1.0) -> dict:
    if not (1 <= duration_seconds <= 5):
        raise ValueError("duration_seconds debe estar entre 1 y 5")

    async with httpx.AsyncClient() as client:
        unloaded_models = await _list_loaded_ollama_models(client)
        for name in unloaded_models:
            await _unload_ollama_model(client, name)

        started_comfyui = False
        proc: subprocess.Popen | None = None
        try:
            if not await _comfyui_is_up(client):
                proc = _start_comfyui_process()
                started_comfyui = True
                await _wait_comfyui_ready(client, timeout=settings.comfyui_startup_timeout)

            seed = random.randint(0, 2**32 - 1)
            workflow = _build_workflow(prompt, duration_seconds, seed)
            prompt_id = await _queue_prompt(client, workflow)

            # Medido en la práctica: un clip de 1s tardó entre ~4.3 y ~14 minutos entre
            # corridas (variación grande, probablemente por presión de RAM/swapping en
            # esta máquina con 34GB) -- el margen tiene que cubrir el peor caso visto,
            # no el promedio.
            generation_timeout = 900 + duration_seconds * 300
            history_entry = await _wait_for_result(client, prompt_id, timeout=generation_timeout)
            output_file = _extract_output_file(history_entry)

            subfolder = output_file.get("subfolder", "")
            output_dir = _comfyui_output_dir()
            path = (output_dir / subfolder / output_file["filename"]) if subfolder else (output_dir / output_file["filename"])

            return {
                "path": str(path),
                "filename": output_file["filename"],
                "duration_seconds": duration_seconds,
                "prompt": prompt,
            }
        finally:
            if started_comfyui and proc is not None:
                _stop_comfyui_process(proc)
            for name in unloaded_models:
                await _reload_ollama_model(client, name)
