"""Tests de la tool de generación de video (app/tools/video_gen.py).

CRÍTICO: nunca se debe arrancar ComfyUI de verdad ni pegarle a Ollama de verdad
en estos tests -- todo lo que hace red o subprocesos reales se mockea con
monkeypatch.
"""

import pytest

from app.tools import video_gen


@pytest.mark.anyio
async def test_generate_video_rejects_duration_out_of_bounds():
    with pytest.raises(ValueError):
        await video_gen.generate_video(prompt="algo", duration_seconds=0.5)
    with pytest.raises(ValueError):
        await video_gen.generate_video(prompt="algo", duration_seconds=6)


@pytest.mark.anyio
async def test_generate_video_happy_path_unloads_and_reloads_ollama(monkeypatch):
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
        return "prompt-123"

    async def _fake_wait_for_result(client, prompt_id, timeout):
        assert prompt_id == "prompt-123"
        return {"outputs": {"16": {"images": [{"filename": "jarvis_gen_1.mp4", "subfolder": ""}]}}}

    def _fail_if_called(*a, **kw):
        raise AssertionError("no debería arrancar/parar ComfyUI si ya estaba corriendo")

    monkeypatch.setattr(video_gen, "_comfyui_is_up", _fake_comfyui_is_up)
    monkeypatch.setattr(video_gen, "_list_loaded_ollama_models", _fake_list_loaded)
    monkeypatch.setattr(video_gen, "_unload_ollama_model", _fake_unload)
    monkeypatch.setattr(video_gen, "_reload_ollama_model", _fake_reload)
    monkeypatch.setattr(video_gen, "_queue_prompt", _fake_queue_prompt)
    monkeypatch.setattr(video_gen, "_wait_for_result", _fake_wait_for_result)
    monkeypatch.setattr(video_gen, "_start_comfyui_process", _fail_if_called)
    monkeypatch.setattr(video_gen, "_stop_comfyui_process", _fail_if_called)

    result = await video_gen.generate_video(prompt="a cat walking", duration_seconds=1)

    assert result["filename"] == "jarvis_gen_1.mp4"
    assert result["path"].endswith("jarvis_gen_1.mp4")
    assert result["duration_seconds"] == 1
    assert calls["unloaded"] == ["jarvis-text-v2"]
    assert calls["reloaded"] == ["jarvis-text-v2"]
    assert calls["queued"] is True


@pytest.mark.anyio
async def test_generate_video_starts_and_stops_comfyui_when_not_running(monkeypatch):
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
        return "prompt-456"

    async def _fake_wait_for_result(client, prompt_id, timeout):
        return {"outputs": {"16": {"videos": [{"filename": "out.mp4", "subfolder": "sub"}]}}}

    monkeypatch.setattr(video_gen, "_comfyui_is_up", _fake_comfyui_is_up)
    monkeypatch.setattr(video_gen, "_start_comfyui_process", _fake_start)
    monkeypatch.setattr(video_gen, "_stop_comfyui_process", _fake_stop)
    monkeypatch.setattr(video_gen, "_wait_comfyui_ready", _fake_wait_ready)
    monkeypatch.setattr(video_gen, "_list_loaded_ollama_models", _fake_list_loaded)
    monkeypatch.setattr(video_gen, "_queue_prompt", _fake_queue_prompt)
    monkeypatch.setattr(video_gen, "_wait_for_result", _fake_wait_for_result)

    result = await video_gen.generate_video(prompt="a dog running", duration_seconds=2)

    assert result["filename"] == "out.mp4"
    assert "sub" in result["path"]
    assert state["started"] is True
    assert state["stopped"] is True


def test_build_workflow_length_is_4k_plus_1():
    workflow = video_gen._build_workflow("a cat", duration_seconds=1, seed=42)
    length = workflow["11"]["inputs"]["length"]
    assert (length - 1) % 4 == 0

    workflow5 = video_gen._build_workflow("a cat", duration_seconds=5, seed=42)
    length5 = workflow5["11"]["inputs"]["length"]
    assert (length5 - 1) % 4 == 0
    assert length5 > length


def test_build_workflow_uses_prompt_text_and_seed():
    workflow = video_gen._build_workflow("a red apple rotating", duration_seconds=1, seed=999)
    assert workflow["9"]["inputs"]["text"] == "a red apple rotating"
    assert workflow["12"]["inputs"]["noise_seed"] == 999
    assert workflow["16"]["inputs"]["filename_prefix"] == "jarvis_gen_999"


def test_extract_output_file_raises_when_no_output():
    with pytest.raises(RuntimeError):
        video_gen._extract_output_file({"outputs": {"16": {}}})


def test_extract_output_file_finds_first_matching_key():
    entry = {"outputs": {"16": {"gifs": [{"filename": "a.mp4", "subfolder": ""}]}}}
    result = video_gen._extract_output_file(entry)
    assert result["filename"] == "a.mp4"
