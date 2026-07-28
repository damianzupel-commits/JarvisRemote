"""Tests de la tool de generación de imágenes (app/tools/image_gen.py).

CRÍTICO: nunca se debe arrancar ComfyUI de verdad ni pegarle a Ollama de verdad
en estos tests -- todo lo que hace red o subprocesos reales se mockea con
monkeypatch.
"""

import pytest

from app.tools import image_gen


@pytest.mark.anyio
async def test_generate_image_happy_path_unloads_and_reloads_ollama(monkeypatch):
    calls = {"unloaded": [], "reloaded": [], "queued": False}

    async def _fake_comfyui_is_up(client):
        return True  # ya estaba corriendo

    async def _fake_list_loaded(client):
        return ["jarvis-text-v2"]

    async def _fake_unload(client, name):
        calls["unloaded"].append(name)

    async def _fake_reload(client, name):
        calls["reloaded"].append(name)

    async def _fake_queue_prompt(client, workflow):
        calls["queued"] = True
        return "prompt-abc"

    async def _fake_wait_for_result(client, prompt_id, timeout):
        assert prompt_id == "prompt-abc"
        return {"outputs": {"9": {"images": [{"filename": "jarvis_img_1.png", "subfolder": ""}]}}}

    def _fail_if_called(*a, **kw):
        raise AssertionError("no debería arrancar/parar ComfyUI si ya estaba corriendo")

    monkeypatch.setattr(image_gen, "comfyui_is_up", _fake_comfyui_is_up)
    monkeypatch.setattr(image_gen, "list_loaded_ollama_models", _fake_list_loaded)
    monkeypatch.setattr(image_gen, "unload_ollama_model", _fake_unload)
    monkeypatch.setattr(image_gen, "reload_ollama_model", _fake_reload)
    monkeypatch.setattr(image_gen, "queue_prompt", _fake_queue_prompt)
    monkeypatch.setattr(image_gen, "wait_for_result", _fake_wait_for_result)
    monkeypatch.setattr(image_gen, "start_comfyui_process", _fail_if_called)
    monkeypatch.setattr(image_gen, "stop_comfyui_process", _fail_if_called)

    result = await image_gen.generate_image(prompt="a cat sitting on a chair", width=512, height=512)

    assert result["filename"] == "jarvis_img_1.png"
    assert result["path"].endswith("jarvis_img_1.png")
    assert result["width"] == 512
    assert result["height"] == 512
    assert calls["unloaded"] == ["jarvis-text-v2"]
    assert calls["reloaded"] == ["jarvis-text-v2"]
    assert calls["queued"] is True


@pytest.mark.anyio
async def test_generate_image_starts_and_stops_comfyui_when_not_running(monkeypatch):
    state = {"up": False, "started": False, "stopped": False}

    async def _fake_comfyui_is_up(client):
        return state["up"]

    def _fake_start(*a, **kw):
        state["started"] = True
        state["up"] = True
        return object()

    def _fake_stop(proc):
        state["stopped"] = True

    async def _fake_wait_ready(client, timeout):
        assert state["up"] is True

    async def _fake_list_loaded(client):
        return []

    async def _fake_queue_prompt(client, workflow):
        return "prompt-xyz"

    async def _fake_wait_for_result(client, prompt_id, timeout):
        return {"outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "sub"}]}}}

    monkeypatch.setattr(image_gen, "comfyui_is_up", _fake_comfyui_is_up)
    monkeypatch.setattr(image_gen, "start_comfyui_process", _fake_start)
    monkeypatch.setattr(image_gen, "stop_comfyui_process", _fake_stop)
    monkeypatch.setattr(image_gen, "wait_comfyui_ready", _fake_wait_ready)
    monkeypatch.setattr(image_gen, "list_loaded_ollama_models", _fake_list_loaded)
    monkeypatch.setattr(image_gen, "queue_prompt", _fake_queue_prompt)
    monkeypatch.setattr(image_gen, "wait_for_result", _fake_wait_for_result)

    result = await image_gen.generate_image(prompt="a dog", width=768, height=768)

    assert result["filename"] == "out.png"
    assert "sub" in result["path"]
    assert state["started"] is True
    assert state["stopped"] is True


def test_round_to_16_snaps_and_clamps():
    assert image_gen._round_to_16(500) == 496 or image_gen._round_to_16(500) == 512
    assert image_gen._round_to_16(512) == 512
    assert image_gen._round_to_16(100) == 256  # clamp al mínimo
    assert image_gen._round_to_16(5000) == 1536  # clamp al máximo
    assert image_gen._round_to_16(768) % 16 == 0


def test_build_workflow_uses_prompt_dimensions_and_seed():
    workflow = image_gen._build_workflow("a red apple", width=512, height=512, seed=777)
    assert workflow["4"]["inputs"]["text"] == "a red apple"
    assert workflow["6"]["inputs"]["width"] == 512
    assert workflow["6"]["inputs"]["height"] == 512
    assert workflow["7"]["inputs"]["seed"] == 777
    assert workflow["9"]["inputs"]["filename_prefix"] == "jarvis_img_777"


def test_build_workflow_uses_flux_dual_clip_loader():
    workflow = image_gen._build_workflow("a cat", width=512, height=512, seed=1)
    assert workflow["2"]["class_type"] == "DualCLIPLoader"
    assert workflow["2"]["inputs"]["type"] == "flux"
    assert workflow["1"]["inputs"]["unet_name"] == "flux1-schnell-Q4_K_S.gguf"
