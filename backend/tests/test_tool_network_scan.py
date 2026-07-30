"""Tests de la tool registrada `nmap_scan` (app/tools/network_scan.py) --
confirma el cableado real: NMAP_ENABLED, el guardrail se aplica ANTES de
correr nmap, y cada intento (aceptado o rechazado) queda auditado."""

from types import SimpleNamespace

import pytest

from app import audit_log
from app.config import settings
from app.network import guardrail
from app.network.models import NetworkScanResult
from app.tools import network_scan


def _fake_result(target: str) -> NetworkScanResult:
    return NetworkScanResult(
        target=target,
        scan_type="quick",
        command=["nmap", "-oX", "-", target],
        started_at="2026-07-29T00:00:00+00:00",
        finished_at="2026-07-29T00:00:01+00:00",
        hosts_up=1,
        findings=[],
        raw_summary="Nmap done: 1 IP address (1 host up) scanned in 1.00 seconds",
    )


def test_nmap_scan_raises_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", False)
    with pytest.raises(network_scan.NmapDisabled):
        network_scan.nmap_scan("127.0.0.1")


def test_nmap_scan_rejects_public_target_without_running_nmap(monkeypatch):
    """El punto central del guardrail: un target público NUNCA debe llegar a
    invocar `run_nmap_scan` -- se corta antes."""
    monkeypatch.setattr(settings, "nmap_enabled", True)
    called = {"ran": False}

    def fake_run_nmap_scan(*args, **kwargs):
        called["ran"] = True
        return _fake_result(args[0] if args else kwargs.get("target"))

    monkeypatch.setattr(network_scan, "run_nmap_scan", fake_run_nmap_scan)

    with pytest.raises(guardrail.TargetNotAuthorizedError):
        network_scan.nmap_scan("8.8.8.8")

    assert called["ran"] is False


def test_nmap_scan_runs_and_returns_dict_for_private_target(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", True)
    monkeypatch.setattr(network_scan, "run_nmap_scan", lambda target, scan_type, timeout: _fake_result(target))

    result = network_scan.nmap_scan("192.168.1.10", scan_type="quick")

    assert result["target"] == "192.168.1.10"
    assert result["hosts_up"] == 1
    assert result["findings"] == []


def test_nmap_scan_audits_rejected_attempt(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", True)

    logged = []
    monkeypatch.setattr(
        audit_log,
        "log_tool_call",
        lambda **kwargs: logged.append(kwargs),
    )

    with pytest.raises(guardrail.TargetNotAuthorizedError):
        network_scan.nmap_scan("8.8.8.8")

    assert len(logged) == 1
    assert logged[0]["tool"] == "nmap_scan"
    assert logged[0]["arguments"]["target"] == "8.8.8.8"
    assert logged[0]["error"] is not None  # ok=False en la línea de auditoría real -- ver audit_log.log_tool_call


def test_nmap_scan_audits_accepted_attempt(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", True)
    monkeypatch.setattr(network_scan, "run_nmap_scan", lambda target, scan_type, timeout: _fake_result(target))

    logged = []
    monkeypatch.setattr(audit_log, "log_tool_call", lambda **kwargs: logged.append(kwargs))

    network_scan.nmap_scan("192.168.1.10")

    assert len(logged) == 1
    assert logged[0]["tool"] == "nmap_scan"
    assert logged[0]["arguments"]["target"] == "192.168.1.10"
    assert logged[0].get("error") is None
    assert logged[0]["result"]["target"] == "192.168.1.10"
