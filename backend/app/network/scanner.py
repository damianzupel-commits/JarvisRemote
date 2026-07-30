"""Wrapper de subprocess sobre nmap real -- mismo patrón que
`security/scanners.py` (subprocess real, salida -> Finding normalizado, nunca
"adivina" hallazgos), pero para reconocimiento de red en vez de código
estático. El guardrail de scope (`network/guardrail.py`) se aplica ANTES de
llegar acá, en `app/tools/network_scan.py` -- este módulo asume que `target`
ya está autorizado.

Sin Npcap instalado (requiere UAC, ver docstring de `app/tools/network_scan.py`
y el README), nmap en Windows NO puede hacer SYN scan (-sS), ping ICMP real
(-sn/-PE) ni detección de SO (-O) -- todo eso necesita sockets crudos. Por eso
todos los `scan_type` de acá usan `-sT` (TCP connect scan, vía la API de
sockets normal de WinSock, sin privilegios especiales) + `-Pn` (no intenta
un ping previo, asume el host arriba -- razonable para escanear infraestructura
propia ya autorizada por el guardrail). `-sV` (detección de servicio/versión)
y `--script vuln` (NSE) funcionan igual sin Npcap: operan sobre la conexión ya
establecida, no necesitan captura de paquetes cruda.

Este módulo también arma (`build_termux_nmap_command`) y parsea
(`parse_phone_scan_result`) escaneos que corren del lado del CELULAR en vez de
la PC (ver `app/tools/network_scan.py::phone_nmap_scan`) -- reusa los mismos
`_SCAN_TYPE_ARGS` y el mismo parser de XML (`_parse_scan_xml`) que el camino de
PC, porque Termux sin root tiene la misma limitación que Windows sin Npcap
(solo TCP connect scan, sin SYN/OS detection), así que los presets son
idénticos. La ejecución real en el celular no pasa por `subprocess` de acá --
la tool arma el string de comando acá pero lo despacha por WebSocket a Termux
vía `phone_run_command` (`app/phone_link.py::dispatch_to_phone`), y le pasa el
stdout/stderr/exit_code que vuelve a `parse_phone_scan_result` de acá para
reusar el mismo parser en vez de duplicarlo.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from .models import NetworkScanResult, PortFinding

_DEFAULT_TIMEOUT_SECONDS = 300.0
_MAX_TIMEOUT_SECONDS = 1200.0

# Presets fijos de argumentos reales de nmap -- a propósito NO se le pasan
# flags arbitrarios de nmap desde la tool call: el LLM elige un `scan_type` de
# esta lista cerrada, nunca un string de flags libre, para no abrir una
# superficie de "argumentos raros de nmap" (ej. -oN escribiendo a una ruta
# arbitraria, --script con un script custom) por fuera de lo que este wrapper
# ya sabe parsear y auditar.
_SCAN_TYPE_ARGS: dict[str, list[str]] = {
    "quick": ["-T4", "-F", "-sT", "-Pn"],
    "version": ["-T4", "-F", "-sT", "-Pn", "-sV", "--version-intensity", "5"],
    "vuln": ["-T4", "-F", "-sT", "-Pn", "-sV", "--script", "vuln"],
    "full": ["-T4", "-p-", "-sT", "-Pn"],
}

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Rutas de instalación por default del instalador oficial de nmap en Windows --
# el instalador no siempre agrega nmap al PATH del sistema, así que además de
# `shutil.which` se prueban estas dos ubicaciones estándar.
_WINDOWS_DEFAULT_PATHS = (
    r"C:\Program Files (x86)\Nmap\nmap.exe",
    r"C:\Program Files\Nmap\nmap.exe",
)


class NmapNotInstalledError(RuntimeError):
    pass


class InvalidScanTypeError(ValueError):
    pass


def _nmap_path() -> str | None:
    found = shutil.which("nmap")
    if found:
        return found
    if sys.platform == "win32":
        for candidate in _WINDOWS_DEFAULT_PATHS:
            if Path(candidate).is_file():
                return candidate
    return None


def is_available() -> bool:
    return _nmap_path() is not None


def _vuln_severity(script_id: str, output: str) -> str | None:
    """Heurística de severidad sobre la salida de un script NSE -- nmap no
    expone una severidad propia (a diferencia de Semgrep/Bandit/Trivy). Los
    scripts de la categoría `vuln` sí siguen una convención real de texto
    ("State: VULNERABLE" / "State: LIKELY VULNERABLE" / "State: NOT VULNERABLE"),
    documentada en https://nmap.org/nsedoc/ -- se lee esa convención en vez de
    inventar una clasificación propia."""
    lowered_id = script_id.lower()
    if "vuln" not in lowered_id and "cve" not in lowered_id:
        return None
    lowered_output = output.lower()
    if "state: vulnerable" in lowered_output:
        return "high"
    if "likely vulnerable" in lowered_output:
        return "medium"
    if "state:" in lowered_output:
        return "info"  # script corrió y no marcó vulnerable, pero es de la categoría vuln -- info, no None
    return None


def _parse_ports(host_el: ET.Element, host_ip: str, hostname: str | None) -> list[PortFinding]:
    findings: list[PortFinding] = []
    ports_el = host_el.find("ports")
    if ports_el is None:
        return findings

    for port_el in ports_el.findall("port"):
        state_el = port_el.find("state")
        state = state_el.get("state", "unknown") if state_el is not None else "unknown"

        service_el = port_el.find("service")
        service = service_el.get("name") if service_el is not None else None
        product = service_el.get("product") if service_el is not None else None
        version = service_el.get("version") if service_el is not None else None

        scripts: list[dict] = []
        severity: str | None = None
        for script_el in port_el.findall("script"):
            script_id = script_el.get("id", "")
            output = script_el.get("output", "")
            scripts.append({"id": script_id, "output": output})
            script_severity = _vuln_severity(script_id, output)
            if script_severity is not None and (
                severity is None or _SEVERITY_RANK.get(script_severity, 9) < _SEVERITY_RANK.get(severity, 9)
            ):
                severity = script_severity

        port_id = port_el.get("portid")
        if port_id is None:
            continue
        findings.append(
            PortFinding(
                host=host_ip,
                hostname=hostname,
                port=int(port_id),
                protocol=port_el.get("protocol", "tcp"),
                state=state,
                service=service,
                product=product,
                version=version,
                severity=severity,
                scripts=scripts,
            )
        )
    return findings


def _parse_scan_xml(
    xml_text: str,
    *,
    target: str,
    scan_type: str,
    command: list[str],
    started_at: str,
    finished_at: str,
) -> NetworkScanResult:
    """Convierte el XML crudo de `nmap -oX -` (venga de un subprocess local o
    del stdout devuelto por Termux) en un `NetworkScanResult` -- compartido
    entre el camino de PC (`run_nmap_scan`) y el de celular
    (`parse_phone_scan_result`) para no duplicar el parseo."""
    try:
        xml_root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise RuntimeError(f"nmap no devolvió XML válido: {exc}") from exc

    findings: list[PortFinding] = []
    hosts_up = 0
    for host_el in xml_root.findall("host"):
        status_el = host_el.find("status")
        if status_el is not None and status_el.get("state") != "up":
            continue
        hosts_up += 1

        addr_el = host_el.find("address[@addrtype='ipv4']")
        if addr_el is None:
            addr_el = host_el.find("address")
        host_ip = addr_el.get("addr", target) if addr_el is not None else target

        hostname_el = host_el.find("hostnames/hostname")
        hostname = hostname_el.get("name") if hostname_el is not None else None

        findings.extend(_parse_ports(host_el, host_ip, hostname))

    finished_stats_el = xml_root.find("runstats/finished")
    raw_summary = finished_stats_el.get("summary", "") if finished_stats_el is not None else ""

    return NetworkScanResult(
        target=target,
        scan_type=scan_type,
        command=command,
        started_at=started_at,
        finished_at=finished_at,
        hosts_up=hosts_up,
        findings=findings,
        raw_summary=raw_summary,
    )


def run_nmap_scan(target: str, scan_type: str = "quick", timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> NetworkScanResult:
    """Corre nmap real contra `target` (YA validado por el guardrail antes de
    llegar acá -- este wrapper no vuelve a chequear scope). `-oX -` pide el
    reporte XML por stdout en vez de a un archivo, más fácil y seguro de
    parsear que la salida de texto libre (sin escribir un archivo temporal
    cuya ruta habría que gestionar)."""
    if scan_type not in _SCAN_TYPE_ARGS:
        raise InvalidScanTypeError(f"scan_type '{scan_type}' inválido -- opciones: {sorted(_SCAN_TYPE_ARGS)}")

    exe = _nmap_path()
    if exe is None:
        raise NmapNotInstalledError(
            "nmap no está instalado en esta PC (o no se encontró en PATH / Program Files). "
            "Instalación manual requerida -- ver backend/README.md, sección nmap (el instalador "
            "de Windows necesita un click de UAC para el driver Npcap, no se puede automatizar "
            "de forma segura). Descarga oficial: https://nmap.org/download.html"
        )

    effective_timeout = min(float(timeout), _MAX_TIMEOUT_SECONDS)
    cmd = [exe, *_SCAN_TYPE_ARGS[scan_type], "-oX", "-", target]

    started_at = datetime.now(timezone.utc).isoformat()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=effective_timeout,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"nmap no terminó en {effective_timeout}s (target={target}, scan_type={scan_type})")
    finished_at = datetime.now(timezone.utc).isoformat()

    try:
        return _parse_scan_xml(
            proc.stdout,
            target=target,
            scan_type=scan_type,
            command=cmd,
            started_at=started_at,
            finished_at=finished_at,
        )
    except RuntimeError as exc:
        raise RuntimeError(f"{exc} (exit={proc.returncode}): {proc.stderr[:1000]}") from exc


class NmapNotInstalledOnPhoneError(RuntimeError):
    """El paquete nmap de Termux no está instalado en el celular."""


_PHONE_NOT_FOUND_MARKERS = (
    "nmap: not found",
    "nmap: command not found",
    "no such file or directory",
)


def build_termux_nmap_command(target: str, scan_type: str = "quick") -> str:
    """Arma el mismo comando de `nmap -oX -` que `run_nmap_scan`, pero como un
    string listo para mandar como `command` a la tool `phone_run_command`
    (que lo corre como `bash -c "<command>"` dentro de Termux) -- usa el
    binario `nmap` tal cual (sin ruta absoluta: se asume en el PATH de Termux,
    que es donde `pkg install nmap` lo deja) en vez de la ruta resuelta de
    `_nmap_path()`, que es específica de la PC. `shlex.join` escapa cada
    argumento (relevante para `target` si es un CIDR u otro string con
    caracteres que el shell podría interpretar)."""
    if scan_type not in _SCAN_TYPE_ARGS:
        raise InvalidScanTypeError(f"scan_type '{scan_type}' inválido -- opciones: {sorted(_SCAN_TYPE_ARGS)}")
    return shlex.join(["nmap", *_SCAN_TYPE_ARGS[scan_type], "-oX", "-", target])


def parse_phone_scan_result(
    phone_result: dict,
    *,
    target: str,
    scan_type: str,
    command: list[str],
    started_at: str,
    finished_at: str,
) -> NetworkScanResult:
    """Convierte el resultado crudo de `phone_run_command` (stdout/stderr/
    exit_code, ver `TermuxCommandRunner.kt`) en un `NetworkScanResult` --
    contraparte de `run_nmap_scan` para el camino de celular. Detecta el caso
    más probable en la práctica (nmap no instalado en Termux todavía) y lo
    convierte en un error explícito en vez de dejar que el parseo de XML
    falle con un mensaje genérico."""
    stdout = phone_result.get("stdout") or ""
    stderr = phone_result.get("stderr") or ""
    exit_code = phone_result.get("exit_code")
    termux_error = phone_result.get("termux_error")

    if termux_error:
        raise RuntimeError(f"Termux rechazó el comando antes de correrlo: {termux_error}")

    lowered = f"{stdout}\n{stderr}".lower()
    if exit_code == 127 or any(marker in lowered for marker in _PHONE_NOT_FOUND_MARKERS):
        raise NmapNotInstalledOnPhoneError(
            "nmap no está instalado en Termux (celular). Desde la app Termux (sin necesitar "
            "root): 'pkg install nmap'. " + (f"stderr: {stderr[:500]}" if stderr else "")
        )

    try:
        return _parse_scan_xml(
            stdout,
            target=target,
            scan_type=scan_type,
            command=command,
            started_at=started_at,
            finished_at=finished_at,
        )
    except RuntimeError as exc:
        raise RuntimeError(f"{exc} (exit_code={exit_code}): {stderr[:1000]}") from exc
