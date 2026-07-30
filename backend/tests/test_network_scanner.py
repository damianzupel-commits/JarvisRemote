"""Tests del wrapper de subprocess sobre nmap (app/network/scanner.py).
Parseo de XML mockeado (sin depender de tener nmap real instalado) + un test
de integración real contra 127.0.0.1 que se saltea si el binario no está
instalado en este entorno (mismo patrón que test_security_scanners.py)."""

from types import SimpleNamespace

import pytest

from app.network import scanner

_FAKE_NMAP_XML_OPEN_PORTS = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="127.0.0.1" addrtype="ipv4"/>
    <hostnames><hostname name="localhost" type="PTR"/></hostnames>
    <ports>
      <port protocol="tcp" portid="22">
        <state state="open"/>
        <service name="ssh" product="OpenSSH" version="8.9"/>
      </port>
      <port protocol="tcp" portid="80">
        <state state="closed"/>
      </port>
    </ports>
  </host>
  <runstats>
    <finished time="1234" summary="Nmap done: 1 IP address (1 host up) scanned in 0.50 seconds"/>
  </runstats>
</nmaprun>
"""

_FAKE_NMAP_XML_VULN_SCRIPT = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="up"/>
    <address addr="192.168.1.50" addrtype="ipv4"/>
    <ports>
      <port protocol="tcp" portid="445">
        <state state="open"/>
        <service name="microsoft-ds"/>
        <script id="smb-vuln-ms17-010" output="Host is likely VULNERABLE to MS17-010!  State: LIKELY VULNERABLE"/>
      </port>
      <port protocol="tcp" portid="443">
        <state state="open"/>
        <service name="https"/>
        <script id="ssl-vuln-example" output="State: VULNERABLE"/>
      </port>
      <port protocol="tcp" portid="8080">
        <state state="open"/>
        <service name="http-proxy"/>
        <script id="http-vuln-example" output="State: NOT VULNERABLE"/>
      </port>
    </ports>
  </host>
  <runstats>
    <finished time="1234" summary="Nmap done: 1 IP address (1 host up) scanned in 12.30 seconds"/>
  </runstats>
</nmaprun>
"""

_FAKE_NMAP_XML_HOST_DOWN = """<?xml version="1.0"?>
<nmaprun>
  <host>
    <status state="down"/>
    <address addr="192.168.1.99" addrtype="ipv4"/>
  </host>
  <runstats>
    <finished time="1234" summary="Nmap done: 1 IP address (0 hosts up) scanned in 3.00 seconds"/>
  </runstats>
</nmaprun>
"""


def _mock_nmap(monkeypatch, stdout, returncode=0):
    def fake_run(cmd, **kwargs):
        return SimpleNamespace(stdout=stdout, stderr="", returncode=returncode)

    monkeypatch.setattr(scanner, "_nmap_path", lambda: "nmap")
    monkeypatch.setattr(scanner.subprocess, "run", fake_run)


def test_run_nmap_scan_parses_open_and_closed_ports(monkeypatch):
    _mock_nmap(monkeypatch, _FAKE_NMAP_XML_OPEN_PORTS)

    result = scanner.run_nmap_scan("127.0.0.1", scan_type="quick")

    assert result.target == "127.0.0.1"
    assert result.hosts_up == 1
    assert len(result.findings) == 2

    ssh = next(f for f in result.findings if f.port == 22)
    assert ssh.state == "open"
    assert ssh.service == "ssh"
    assert ssh.product == "OpenSSH"
    assert ssh.version == "8.9"
    assert ssh.hostname == "localhost"
    assert ssh.severity is None

    http = next(f for f in result.findings if f.port == 80)
    assert http.state == "closed"


def test_run_nmap_scan_derives_severity_from_vuln_scripts(monkeypatch):
    _mock_nmap(monkeypatch, _FAKE_NMAP_XML_VULN_SCRIPT)

    result = scanner.run_nmap_scan("192.168.1.50", scan_type="vuln")

    smb = next(f for f in result.findings if f.port == 445)
    assert smb.severity == "medium"  # "LIKELY VULNERABLE"
    assert smb.scripts[0]["id"] == "smb-vuln-ms17-010"

    ssl = next(f for f in result.findings if f.port == 443)
    assert ssl.severity == "high"  # "State: VULNERABLE"

    http_proxy = next(f for f in result.findings if f.port == 8080)
    assert http_proxy.severity == "info"  # corrió, no vulnerable, pero categoría vuln


def test_run_nmap_scan_reports_zero_findings_for_down_host(monkeypatch):
    _mock_nmap(monkeypatch, _FAKE_NMAP_XML_HOST_DOWN)

    result = scanner.run_nmap_scan("192.168.1.99", scan_type="quick")

    assert result.hosts_up == 0
    assert result.findings == []


def test_run_nmap_scan_raises_when_binary_missing(monkeypatch):
    monkeypatch.setattr(scanner, "_nmap_path", lambda: None)
    with pytest.raises(scanner.NmapNotInstalledError):
        scanner.run_nmap_scan("127.0.0.1")


def test_run_nmap_scan_raises_on_invalid_scan_type():
    with pytest.raises(scanner.InvalidScanTypeError):
        scanner.run_nmap_scan("127.0.0.1", scan_type="not-a-real-type")


def test_run_nmap_scan_raises_on_invalid_xml(monkeypatch):
    _mock_nmap(monkeypatch, "not xml at all")
    with pytest.raises(RuntimeError):
        scanner.run_nmap_scan("127.0.0.1")


def test_scan_type_args_never_include_privileged_flags():
    """Sin Npcap (requiere UAC, no instalable de forma automatizada -- ver
    docstring del módulo), nmap en Windows no puede hacer SYN scan (-sS) ni
    ping ICMP real (-sn/-PE) ni detección de SO (-O). Confirma que ningún
    preset pide esos flags -- todos tienen que quedarse en -sT + -Pn."""
    for scan_type, args in scanner._SCAN_TYPE_ARGS.items():
        assert "-sT" in args, scan_type
        assert "-Pn" in args, scan_type
        assert "-sS" not in args, scan_type
        assert "-O" not in args, scan_type


def test_build_termux_nmap_command_uses_bare_nmap_and_quotes_target():
    """A diferencia de `run_nmap_scan` (que resuelve una ruta absoluta con
    `_nmap_path()`, específica de la PC), el comando para Termux usa el
    binario `nmap` tal cual -- se asume en el PATH de Termux (`pkg install
    nmap` lo deja ahí)."""
    command = scanner.build_termux_nmap_command("192.168.1.0/24", scan_type="quick")

    assert command.startswith("nmap ")
    assert "192.168.1.0/24" in command
    assert "-oX" in command
    assert "-sT" in command and "-Pn" in command


def test_build_termux_nmap_command_raises_on_invalid_scan_type():
    with pytest.raises(scanner.InvalidScanTypeError):
        scanner.build_termux_nmap_command("192.168.1.1", scan_type="not-a-real-type")


def test_parse_phone_scan_result_parses_successful_xml():
    phone_result = {"stdout": _FAKE_NMAP_XML_OPEN_PORTS, "stderr": "", "exit_code": 0}

    result = scanner.parse_phone_scan_result(
        phone_result,
        target="127.0.0.1",
        scan_type="quick",
        command=["nmap", "-oX", "-", "127.0.0.1"],
        started_at="2026-07-29T00:00:00+00:00",
        finished_at="2026-07-29T00:00:01+00:00",
    )

    assert result.hosts_up == 1
    assert len(result.findings) == 2


def test_parse_phone_scan_result_detects_missing_nmap_package():
    """El caso más probable en la práctica: Termux sin `pkg install nmap`
    corrido todavía -- tiene que fallar con un mensaje explícito, no con un
    error genérico de XML inválido."""
    phone_result = {
        "stdout": "",
        "stderr": "bash: line 1: nmap: command not found",
        "exit_code": 127,
    }

    with pytest.raises(scanner.NmapNotInstalledOnPhoneError, match="pkg install nmap"):
        scanner.parse_phone_scan_result(
            phone_result,
            target="192.168.1.1",
            scan_type="quick",
            command=["nmap", "-oX", "-", "192.168.1.1"],
            started_at="2026-07-29T00:00:00+00:00",
            finished_at="2026-07-29T00:00:01+00:00",
        )


def test_parse_phone_scan_result_raises_on_termux_plugin_error():
    """`errmsg` (mapeado acá a `termux_error`) es la señal confiable de que
    Termux rechazó el comando a nivel plugin (permiso, config) -- ver
    docstring de TermuxCommandRunner.kt."""
    phone_result = {"termux_error": "Missing RUN_COMMAND permission"}

    with pytest.raises(RuntimeError, match="Missing RUN_COMMAND permission"):
        scanner.parse_phone_scan_result(
            phone_result,
            target="192.168.1.1",
            scan_type="quick",
            command=["nmap", "-oX", "-", "192.168.1.1"],
            started_at="2026-07-29T00:00:00+00:00",
            finished_at="2026-07-29T00:00:01+00:00",
        )


def test_parse_phone_scan_result_raises_on_invalid_xml():
    phone_result = {"stdout": "not xml at all", "stderr": "", "exit_code": 0}

    with pytest.raises(RuntimeError):
        scanner.parse_phone_scan_result(
            phone_result,
            target="192.168.1.1",
            scan_type="quick",
            command=["nmap", "-oX", "-", "192.168.1.1"],
            started_at="2026-07-29T00:00:00+00:00",
            finished_at="2026-07-29T00:00:01+00:00",
        )


@pytest.mark.timeout(60)
def test_run_nmap_scan_real_localhost():
    """Escaneo real (no mockeado) contra 127.0.0.1 -- se saltea si nmap no
    está instalado en este entorno (mismo patrón que
    test_security_scanners.py con bandit/semgrep/cppcheck)."""
    if not scanner.is_available():
        pytest.skip("nmap no está instalado en este entorno")

    result = scanner.run_nmap_scan("127.0.0.1", scan_type="quick", timeout=60)

    assert result.target == "127.0.0.1"
    assert result.hosts_up == 1
    assert result.raw_summary  # nmap siempre deja la línea final "Nmap done: ..."
