import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def malware_settings(monkeypatch, tmp_path):
    """Redirige TODOS los paths en disco que usa app/malware/ a tmp_path --
    reusada por todos los test_malware_*.py para no repetir el mismo bloque
    de monkeypatch.setattr en cada archivo. No toca malware_yara_rules_dir
    (se deja el set real de app/malware/rules/, justamente lo que hay que
    ejercitar de verdad en los tests de detección)."""
    from app.config import settings

    monkeypatch.setattr(settings, "malware_log_path", str(tmp_path / "data" / "malware_log.jsonl"))
    monkeypatch.setattr(settings, "malware_quarantine_dir", str(tmp_path / "data" / "quarantine"))
    monkeypatch.setattr(settings, "malware_integrity_baseline_path", str(tmp_path / "data" / "baseline.json"))
    monkeypatch.setattr(settings, "investigation_artifact_store_dir", str(tmp_path / "data" / "artifacts"))
    monkeypatch.setattr(settings, "investigation_keys_dir", str(tmp_path / "data" / "keys"))
    monkeypatch.setattr(settings, "virustotal_cache_path", str(tmp_path / "data" / "vt_cache.json"))
    monkeypatch.setattr(settings, "clamav_enabled", False)
    return settings


@pytest.fixture(autouse=True)
def _no_real_embeddings(monkeypatch):
    """La suite corre 100% offline por default -- sin esto, cada
    `vault.save_note`/`search_notes` de cualquier test pegaría contra un LM
    Studio real (ver app/obsidian/embeddings.py), lo que rompe la
    convención del proyecto (nada de servicios externos en tests) y de paso
    haría la suite lenta/flaky en máquinas sin LM Studio corriendo. Los
    tests que sí prueban similitud semántica reemplazan esto con vectores
    fake, o restauran la función real de forma explícita para el único test
    de integración que pega contra el modelo real (ver
    test_obsidian_embeddings.py / test_obsidian_vault.py)."""
    from app.obsidian import embeddings

    monkeypatch.setattr(embeddings, "get_embedding", lambda text: None)
