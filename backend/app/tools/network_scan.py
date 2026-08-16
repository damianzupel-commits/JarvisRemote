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

Este módulo también define `phone_nmap_scan`, la contraparte que escanea
desde el CELULAR en vez de la PC -- necesaria porque el backend corre en la
PC de casa del usuario, que no tiene visibilidad de ninguna red a la que el
celular esté conectado (dos redes físicas separadas: que el celular chatee
con Jarvis por Tailscale no significa que la PC pueda "ver" la wifi en la que
el celular está en ese momento). Para auditar una red de un tercero (ej. la
wifi de un local que le dio la contraseña al usuario) sin instalar nada ni
llevar una notebook, el escaneo tiene que correr DESDE el dispositivo que
está conectado a esa red -- el celular. `phone_nmap_scan` reusa el mismo
guardrail de scope que `nmap_scan` (`resolve_and_authorize`, ver arriba): el
criterio de "¿tenés autorización para escanear esto?" es el mismo sin
importar desde qué dispositivo se dispara -- correr desde el celular no
relaja el guardrail, y en la práctica el guardrail sigue siendo válido porque
un target autorizado (IP/CIDR privado, o una whitelist explícita) se valida
por su propio valor, no por qué tan "visible" es desde la PC (no hace falta
resolución DNS para una IP/CIDR literal). Y reusa el MISMO mecanismo real de
ejecución que `phone_run_command` (`app/phone_link.py::dispatch_to_phone`,
Termux vía su Intent RUN_COMMAND) en vez de inventar un canal nuevo -- este
módulo arma el comando de nmap y parsea el resultado (`app/network/scanner.py`
:: `build_termux_nmap_command` / `parse_phone_scan_result`), pero quien
ejecuta de verdad es el mismo Termux del celular que ya usa `phone_run_command`.
Requiere que el celular tenga el paquete `nmap` de Termux instalado (`pkg
install nmap`, sin necesitar root -- soporta TCP connect scan y NSE, no SYN
scan/OS detection, misma limitación que la PC sin Npcap); si no está
instalado, la tool falla con un mensaje explícito en vez de asumir que corrió.
"""

from __future__ import annotations

import shlex
from datetime import datetime, timezone

from .. import audit_log, phone_link
from ..config import settings
from ..network.guardrail import TargetNotAuthorizedError, resolve_and_authorize
from ..network.scanner import (
    _DEFAULT_TIMEOUT_SECONDS,
    _MAX_TIMEOUT_SECONDS,
    InvalidScanTypeError,
    build_termux_nmap_command,
    parse_phone_scan_result,
    run_nmap_scan,
)
from . import register_tool


class NmapDisabled(RuntimeError):
    pass


class PhoneNmapDisabled(RuntimeError):
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
        # Usar la IP YA RESUELTA por el gate para el escaneo real (no el
        # `target` original si era un hostname) -- bug real de DNS
        # rebinding arreglado 2026-08-13, ver docstring de
        # resolve_and_authorize. Nunca volver a pasarle el hostname crudo
        # a run_nmap_scan, que lo resolvería de nuevo por su cuenta.
        authorized_target = resolve_and_authorize(target)
    except TargetNotAuthorizedError as exc:
        # El campo "error" (y por lo tanto ok=False) en esta línea de auditoría
        # ES el registro de "rechazado por el guardrail" -- mismo mecanismo que
        # usa pc_run_command para su blocklist, no hace falta un campo aparte.
        audit_log.log_tool_call(target="pc", tool="nmap_scan", arguments=arguments, error=str(exc))
        raise

    try:
        result = run_nmap_scan(authorized_target, scan_type=scan_type, timeout=timeout)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="nmap_scan", arguments=arguments, error=str(exc))
        raise

    result_dict = result.to_dict()
    audit_log.log_tool_call(target="pc", tool="nmap_scan", arguments=arguments, result=result_dict)
    return result_dict


@register_tool(
    name="phone_nmap_scan",
    description=(
        "Corre un escaneo de red REAL con nmap, pero ejecutado DESDE EL CELULAR (vía Termux) en vez "
        "de la PC -- usar esta tool (no nmap_scan) cuando el objetivo esté en una red a la que solo el "
        "celular está conectado en este momento (ej. la wifi de un local/restaurante/oficina de un "
        "tercero, o cualquier red que no sea la LAN de casa de la PC): el backend corre en la PC, que "
        "NO tiene visibilidad de esa red aunque el celular esté chateando con Jarvis por Tailscale -- "
        "son dos redes físicas separadas, y solo un dispositivo conectado de verdad a esa red (el "
        "celular) puede escanearla. Para la LAN de casa/infraestructura propia de la PC, usar nmap_scan "
        "en vez de esta. MISMO GUARDRAIL DE SCOPE NO NEGOCIABLE que nmap_scan (correr desde el celular "
        "no lo relaja): por default SOLO rangos privados/reservados (10.0.0.0/8, 172.16.0.0/12, "
        "192.168.0.0/16), loopback (127.0.0.0/8) o Tailscale (100.64.0.0/10) -- cualquier IP/dominio "
        "PÚBLICO se rechaza antes de ejecutar nada salvo que el usuario lo haya agregado a mano a "
        "NMAP_AUTHORIZED_TARGETS en backend/.env. Si el usuario pide escanear algo fuera de ese "
        "alcance, RECHAZALO vos mismo explicando por qué (mismo criterio legal que nmap_scan: escanear "
        "sistemas que no son tuyos y sin autorización explícita del dueño puede ser ilegal) -- ni "
        "siquiera aunque el pedido sea 'con permiso del dueño del local': esa autorización la valida "
        "el USUARIO agregando el target a NMAP_AUTHORIZED_TARGETS, no una afirmación en el chat. "
        "Requiere que el celular esté conectado a Jarvis (mismo requisito que cualquier tool phone_*) Y "
        "tenga el paquete nmap de Termux instalado ('pkg install nmap' dentro de Termux, sin necesitar "
        "root) -- si falta, la tool falla con un mensaje explicando exactamente eso, decíselo al "
        "usuario tal cual en vez de asumir que corrió. Por no tener root, soporta TCP connect scan y "
        "detección de servicio/NSE igual que la PC sin Npcap, pero no SYN scan ni detección de SO."
    ),
    parameters={
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": (
                    "IP, hostname simple o rango CIDR a escanear DENTRO de la red actual del celular "
                    "(ej. '192.168.1.10', '192.168.1.0/24'). NO soporta rangos con guión "
                    "('10.0.0.1-50') ni wildcards ('10.0.0.*') ni varios targets en un mismo string."
                ),
            },
            "scan_type": {
                "type": "string",
                "enum": ["quick", "version", "vuln", "full"],
                "description": (
                    "'quick' (default): top 100 puertos TCP, rápido. 'version': igual + detección de "
                    "servicio/versión (-sV). 'vuln': igual que version + scripts NSE de vulnerabilidades "
                    "conocidas (--script vuln), más lento. 'full': los 65535 puertos TCP, puede tardar "
                    "varios minutos -- considerar que corre sobre datos móviles/wifi ajena, puede ser "
                    "más lento que en la PC."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": (
                    f"Segundos a esperar antes de cortar el escaneo (default {int(_DEFAULT_TIMEOUT_SECONDS)}, "
                    f"tope duro {int(_MAX_TIMEOUT_SECONDS)})."
                ),
            },
        },
        "required": ["target"],
    },
)
async def phone_nmap_scan(target: str, scan_type: str = "quick", timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Handler real (a diferencia de las tools de `tools/phone.py`, esta NO se
    registra con `target="phone"` -- corre acá en el backend porque necesita
    aplicar el guardrail y parsear el XML de resultado, y desde acá dispara
    manualmente `phone_link.dispatch_to_phone("phone_run_command", ...)` para
    reusar el mismo canal real de ejecución que `phone_run_command` en vez de
    inventar uno nuevo del lado de Android. Esa llamada interna ya aplica por
    su cuenta el gate de PHONE_SHELL_ENABLED y el blocklist de comandos
    destructivos de `phone_link` -- no hace falta duplicarlos acá."""
    arguments = {"target": target, "scan_type": scan_type, "timeout": timeout}

    if not settings.nmap_enabled:
        error = "phone_nmap_scan deshabilitada. Setear NMAP_ENABLED=true en backend/.env para habilitarla."
        audit_log.log_tool_call(target="phone", tool="phone_nmap_scan", arguments=arguments, error=error)
        raise PhoneNmapDisabled(error)

    try:
        # Mismo fix real de DNS rebinding que nmap_scan (ver docstring de
        # resolve_and_authorize) -- usa la IP ya resuelta por el gate, no
        # el hostname original. Nota de trade-off real: la resolución acá
        # la hace la PC (donde vive el guardrail), no el celular -- para
        # un hostname que solo resuelve DENTRO de la red del celular (ej.
        # un nombre mDNS/.local de esa wifi puntual), esto podría no ser
        # el mismo resultado que resolvería el celular. Se prioriza cerrar
        # el hueco de seguridad real (confirmado explotable) sobre ese
        # caso borde de hostnames locales al celular, que sigue siendo
        # infrecuente frente al uso real (targets por IP directa dentro
        # del rango privado, sin resolución de por medio en absoluto).
        authorized_target = resolve_and_authorize(target)
    except TargetNotAuthorizedError as exc:
        audit_log.log_tool_call(target="phone", tool="phone_nmap_scan", arguments=arguments, error=str(exc))
        raise

    try:
        command_str = build_termux_nmap_command(authorized_target, scan_type=scan_type)
    except InvalidScanTypeError as exc:
        audit_log.log_tool_call(target="phone", tool="phone_nmap_scan", arguments=arguments, error=str(exc))
        raise

    effective_timeout = min(float(timeout), _MAX_TIMEOUT_SECONDS)
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        phone_result = await phone_link.dispatch_to_phone(
            "phone_run_command",
            {"command": command_str, "timeout": int(effective_timeout)},
            timeout=effective_timeout + 10,
        )
    except Exception as exc:
        audit_log.log_tool_call(target="phone", tool="phone_nmap_scan", arguments=arguments, error=str(exc))
        raise
    finished_at = datetime.now(timezone.utc).isoformat()

    try:
        result = parse_phone_scan_result(
            phone_result,
            target=target,
            scan_type=scan_type,
            command=shlex.split(command_str),
            started_at=started_at,
            finished_at=finished_at,
        )
    except Exception as exc:
        audit_log.log_tool_call(target="phone", tool="phone_nmap_scan", arguments=arguments, error=str(exc))
        raise

    result_dict = result.to_dict()
    audit_log.log_tool_call(target="phone", tool="phone_nmap_scan", arguments=arguments, result=result_dict)
    return result_dict
