"""Tool de reconocimiento de red REAL (`nmap_scan`) -- a diferencia de TODO
el resto del pipeline de seguridad de Jarvis (`security_scan_project`,
`quality_scan_project`: SAST/SCA puro, solo lee código/manifiestos en disco),
esta tool corre nmap de verdad contra sistemas en RED. Es coherente con el
principio de que una herramienta de protección necesita entender también cómo
se ataca (red team informa al blue team -- mismo espíritu que un pentest
profesional), PERO el límite de seguridad tiene que ser más estricto que
cualquier otra tool ya construida en este proyecto, porque acá sí hay una red
real de por medio, no solo archivos locales.

GUARDRAIL NO NEGOCIABLE (`app/network/guardrail.py::resolve_and_authorize`,
aplicado ANTES de ejecutar nada): por default esta tool SOLO puede escanear
rangos privados/reservados (RFC1918: 10.0.0.0/8, 172.16.0.0/12,
192.168.0.0/16), loopback (127.0.0.0/8), o el rango fijo de Tailscale
(100.64.0.0/10). Cualquier IP/dominio público se RECHAZA con
`TargetNotAuthorizedError`, salvo que el usuario lo haya agregado a mano a
`NMAP_AUTHORIZED_TARGETS` en `backend/.env` -- ni esta tool ni el LLM pueden
ampliar esa whitelist con ningún argumento de la tool call. Escanear una
IP/dominio que no es tuyo y sin autorización explícita del dueño puede ser
ilegal (leyes de acceso no autorizado / computer fraud en la mayoría de
países) -- ver `SYSTEM_PROMPT` en `app/agent.py` para la instrucción explícita
de que el LLM debe rechazar ese tipo de pedido él mismo, en vez de intentarlo.
"""

from __future__ import annotations

from .. import audit_log
from ..config import settings
from ..network.guardrail import TargetNotAuthorizedError, resolve_and_authorize
from ..network.scanner import _DEFAULT_TIMEOUT_SECONDS, _MAX_TIMEOUT_SECONDS, run_nmap_scan
from . import register_tool


class NmapDisabled(RuntimeError):
    pass


@register_tool(
    name="nmap_scan",
    description=(
        "Corre un escaneo de red REAL con nmap contra un host/rango -- puertos abiertos, servicios, "
        "versiones y (con scan_type='vuln') scripts NSE de detección de vulnerabilidades conocidas. "
        "GUARDRAIL DE SCOPE NO NEGOCIABLE: por default SOLO se puede escanear rangos privados/reservados "
        "(10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), loopback (127.0.0.0/8) o el rango fijo de Tailscale "
        "(100.64.0.0/10) -- cualquier IP/dominio PÚBLICO se rechaza con un error ANTES de ejecutar nada, "
        "salvo que el usuario lo haya agregado a mano a NMAP_AUTHORIZED_TARGETS en backend/.env (ni esta "
        "tool ni vos pueden ampliar esa whitelist con ningún argumento). Si el usuario pide escanear algo "
        "fuera de ese alcance (una IP pública, un dominio de terceros, 'la red de mi vecino', etc.), "
        "RECHAZALO vos mismo explicando por qué en vez de intentarlo o pedir confirmación blanda: escanear "
        "sistemas que no son tuyos y sin autorización explícita del dueño puede ser ilegal (leyes de acceso "
        "no autorizado / computer fraud en la mayoría de países). Usalo para auditar tu propia red/LAN/"
        "infraestructura, no para reconocimiento ofensivo de terceros. Requiere nmap instalado en la PC "
        "(instalación manual, no automatizable -- si falla con 'nmap no está instalado', decíselo al "
        "usuario tal cual)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": (
                    "IP, hostname simple o rango CIDR a escanear (ej. '192.168.1.10', '192.168.1.0/24', "
                    "'localhost'). NO soporta rangos con guión ('10.0.0.1-50') ni wildcards ('10.0.0.*') "
                    "ni varios targets en un mismo string -- un target por llamada."
                ),
            },
            "scan_type": {
                "type": "string",
                "enum": ["quick", "version", "vuln", "full"],
                "description": (
                    "'quick' (default): top 100 puertos TCP, rápido. 'version': igual + detección de "
                    "servicio/versión (-sV). 'vuln': igual que version + scripts NSE de vulnerabilidades "
                    "conocidas (--script vuln), más lento. 'full': los 65535 puertos TCP, puede tardar "
                    "varios minutos."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": (
                    f"Segundos a esperar antes de cortar el escaneo (default {int(_DEFAULT_TIMEOUT_SECONDS)}, "
                    f"tope duro {int(_MAX_TIMEOUT_SECONDS)} sin importar lo que se pida -- 'full' sobre "
                    "muchos hosts puede necesitar acercarse al tope)."
                ),
            },
        },
        "required": ["target"],
    },
)
def nmap_scan(target: str, scan_type: str = "quick", timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> dict:
    arguments = {"target": target, "scan_type": scan_type, "timeout": timeout}

    if not settings.nmap_enabled:
        error = "nmap_scan deshabilitada. Setear NMAP_ENABLED=true en backend/.env para habilitarla."
        audit_log.log_tool_call(target="pc", tool="nmap_scan", arguments=arguments, error=error)
        raise NmapDisabled(error)

    try:
        resolve_and_authorize(target)
    except TargetNotAuthorizedError as exc:
        # El campo "error" (y por lo tanto ok=False) en esta línea de auditoría
        # ES el registro de "rechazado por el guardrail" -- mismo mecanismo que
        # usa pc_run_command para su blocklist, no hace falta un campo aparte.
        audit_log.log_tool_call(target="pc", tool="nmap_scan", arguments=arguments, error=str(exc))
        raise

    try:
        result = run_nmap_scan(target, scan_type=scan_type, timeout=timeout)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="nmap_scan", arguments=arguments, error=str(exc))
        raise

    result_dict = result.to_dict()
    audit_log.log_tool_call(target="pc", tool="nmap_scan", arguments=arguments, result=result_dict)
    return result_dict
