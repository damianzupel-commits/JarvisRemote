"""Tests de las tools registradas `nmap_scan`/`phone_nmap_scan`
(app/tools/network_scan.py) -- confirma el cableado real: NMAP_ENABLED, el
guardrail se aplica ANTES de correr nmap, y cada intento (aceptado o
rechazado) queda auditado. Los tests de `phone_nmap_scan` además confirman
que reusa el mismo canal real de `phone_run_command`
(`phone_link.dispatch_to_phone`) en vez de uno nuevo, y que un target público
NUNCA llega a mandarse al celular."""

from types import SimpleNamespace

import pytest

from app import audit_log, phone_link
from app.config import settings
from app.network import guardrail, scanner
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


def test_nmap_scan_uses_the_pinned_ip_not_the_original_hostname(monkeypatch):
    """Regresión end-to-end del bug real de DNS rebinding arreglado
    2026-08-13: nmap_scan tiene que pasarle a run_nmap_scan la IP YA
    resuelta por el gate, nunca el hostname original (que run_nmap_scan/
    nmap resolvería de nuevo por su cuenta, en un momento distinto)."""
    monkeypatch.setattr(settings, "nmap_enabled", True)
    monkeypatch.setattr(guardrail.socket, "gethostbyname", lambda name: "192.168.1.77")
    captured = {}

    def fake_run_nmap_scan(target, scan_type, timeout):
        captured["target"] = target
        return _fake_result(target)

    monkeypatch.setattr(network_scan, "run_nmap_scan", fake_run_nmap_scan)

    network_scan.nmap_scan("mi-router.local")

    assert captured["target"] == "192.168.1.77"  # la IP pinneada, NUNCA "mi-router.local"


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


_FAKE_PHONE_NMAP_XML = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="192.168.1.50" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="80">
        <state state="open"/>
        <service name="http"/>
      </port>
    </ports>
  </host>
  <runstats>
    <finished time="1234" summary="Nmap done: 1 IP address (1 host up) scanned in 1.00 seconds"/>
  </runstats>
</nmaprun>
"""


def _make_fake_dispatch(result=None, exc=None, calls=None):
    async def fake_dispatch(tool_name, arguments, timeout=None):
        if calls is not None:
            calls.append({"tool_name": tool_name, "arguments": arguments, "timeout": timeout})
        if exc is not None:
            raise exc
        return result

    return fake_dispatch


@pytest.mark.anyio
async def test_phone_nmap_scan_raises_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", False)
    with pytest.raises(network_scan.PhoneNmapDisabled):
        await network_scan.phone_nmap_scan("127.0.0.1")


@pytest.mark.anyio
async def test_phone_nmap_scan_rejects_public_target_without_dispatching(monkeypatch):
    """Mismo punto central que nmap_scan, pero para el camino de celular: un
    target público NUNCA debe llegar a mandarse por WebSocket/Termux."""
    monkeypatch.setattr(settings, "nmap_enabled", True)
    calls = []
    monkeypatch.setattr(phone_link, "dispatch_to_phone", _make_fake_dispatch(calls=calls))

    with pytest.raises(guardrail.TargetNotAuthorizedError):
        await network_scan.phone_nmap_scan("8.8.8.8")

    assert calls == []


@pytest.mark.anyio
async def test_phone_nmap_scan_reuses_phone_run_command_dispatch(monkeypatch):
    """Confirma que reusa el MISMO canal real que `phone_run_command` (no uno
    nuevo): el nombre de tool despachado tiene que ser literalmente
    'phone_run_command', con un 'command' de shell armado a partir de nmap."""
    monkeypatch.setattr(settings, "nmap_enabled", True)
    calls = []
    fake_result = {"stdout": _FAKE_PHONE_NMAP_XML, "stderr": "", "exit_code": 0}
    monkeypatch.setattr(phone_link, "dispatch_to_phone", _make_fake_dispatch(result=fake_result, calls=calls))

    result = await network_scan.phone_nmap_scan("192.168.1.50", scan_type="quick")

    assert len(calls) == 1
    assert calls[0]["tool_name"] == "phone_run_command"
    assert "nmap" in calls[0]["arguments"]["command"]
    assert "192.168.1.50" in calls[0]["arguments"]["command"]
    assert "timeout" in calls[0]["arguments"]

    assert result["target"] == "192.168.1.50"
    assert result["hosts_up"] == 1
    assert len(result["findings"]) == 1
    assert result["findings"][0]["port"] == 80


@pytest.mark.anyio
async def test_phone_nmap_scan_reports_missing_nmap_package(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", True)
    fake_result = {"stdout": "", "stderr": "bash: line 1: nmap: command not found", "exit_code": 127}
    monkeypatch.setattr(phone_link, "dispatch_to_phone", _make_fake_dispatch(result=fake_result))

    with pytest.raises(scanner.NmapNotInstalledOnPhoneError, match="pkg install nmap"):
        await network_scan.phone_nmap_scan("192.168.1.50")


@pytest.mark.anyio
async def test_phone_nmap_scan_propagates_phone_not_connected(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", True)
    monkeypatch.setattr(
        phone_link,
        "dispatch_to_phone",
        _make_fake_dispatch(exc=phone_link.PhoneNotConnectedError("no hay celular conectado")),
    )

    with pytest.raises(phone_link.PhoneNotConnectedError):
        await network_scan.phone_nmap_scan("192.168.1.50")


@pytest.mark.anyio
async def test_phone_nmap_scan_audits_rejected_attempt(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", True)
    logged = []
    monkeypatch.setattr(audit_log, "log_tool_call", lambda **kwargs: logged.append(kwargs))

    with pytest.raises(guardrail.TargetNotAuthorizedError):
        await network_scan.phone_nmap_scan("8.8.8.8")

    assert len(logged) == 1
    assert logged[0]["tool"] == "phone_nmap_scan"
    assert logged[0]["target"] == "phone"
    assert logged[0]["arguments"]["target"] == "8.8.8.8"
    assert logged[0]["error"] is not None


@pytest.mark.anyio
async def test_phone_nmap_scan_audits_accepted_attempt(monkeypatch):
    monkeypatch.setattr(settings, "nmap_enabled", True)
    fake_result = {"stdout": _FAKE_PHONE_NMAP_XML, "stderr": "", "exit_code": 0}
    monkeypatch.setattr(phone_link, "dispatch_to_phone", _make_fake_dispatch(result=fake_result))

    logged = []
    monkeypatch.setattr(audit_log, "log_tool_call", lambda **kwargs: logged.append(kwargs))

    await network_scan.phone_nmap_scan("192.168.1.50")

    assert len(logged) == 1
    assert logged[0]["tool"] == "phone_nmap_scan"
    assert logged[0]["target"] == "phone"
    assert logged[0].get("error") is None
    assert logged[0]["result"]["target"] == "192.168.1.50"
