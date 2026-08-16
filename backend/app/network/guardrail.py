"""Guardrail de scope para TODAS las tools de pentesting activo del
proyecto (nmap_scan/phone_nmap_scan ya migrados; sqlmap/tshark/metasploit/
zap/nessus lo reusan a medida que se agregan, ver spec de pentesting
2026-08-13) -- a diferencia del resto del pipeline de seguridad de Jarvis
(SAST/SCA puro, solo lee código/manifiestos en disco), estas tools actúan
contra sistemas de RED reales. Escanear/atacar una IP/dominio que no es
tuyo y sin autorización explícita del dueño puede ser ilegal (Ley 26.388 en
Argentina, leyes de acceso no autorizado / computer fraud en la mayoría de
países) -- por eso esto es un guardrail TÉCNICO real (rechazo duro antes de
ejecutar nada), no solo una instrucción de system prompt: ni la tool ni el
LLM pueden bypassearlo con ningún argumento de la tool call, y "el usuario
dijo que sí en el chat" NUNCA es un camino de autorización válido -- la
única forma real es que el USUARIO edite `authorized_targets.yaml` (o,
retrocompatible, `NMAP_AUTHORIZED_TARGETS` en `.env`) a mano, fuera del
chat. Ver `config.py::authorized_targets_path`.

Scope permitido por default (sin tocar ninguna config):
  - RFC 1918 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  - loopback (127.0.0.0/8)
  - el rango fijo de Tailscale (100.64.0.0/10) -- reusado de
    `network_info.TAILSCALE_RANGE` en vez de redefinido, para que las dos
    nociones de "es Tailscale" del proyecto no puedan divergir.

Cualquier otro target (IP pública, o un hostname que resuelva a una) se
rechaza salvo que caiga dentro de `authorized_targets.yaml` o
`settings.nmap_authorized_targets` (env var, retrocompatibilidad).

Un target en la whitelist NO necesita estar corriendo/alcanzable en este
momento para estar "autorizado" -- los laboratorios (PyGoat/NodeGoat/etc.)
se levantan bajo demanda, decisión de Damian 2026-08-13. Este módulo solo
valida pertenencia a un rango permitido (resolución de IP/CIDR/hostname),
nunca intenta conectarse ni verificar que el target esté vivo -- esa
responsabilidad es de cada tool en el momento de ejecutar, no del gate.
"""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path

import yaml

from ..config import settings
from ..network_info import TAILSCALE_RANGE

_IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

_RFC1918_RANGES: list[_IPNetwork] = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]
_LOOPBACK_RANGE = ipaddress.ip_network("127.0.0.0/8")

_DEFAULT_SCOPE_RANGES: list[_IPNetwork] = [*_RFC1918_RANGES, _LOOPBACK_RANGE, TAILSCALE_RANGE]


class TargetNotAuthorizedError(PermissionError):
    """El target no cae en el scope privado/loopback/Tailscale por default,
    en `authorized_targets.yaml`, ni en `NMAP_AUTHORIZED_TARGETS`."""


def _parse_yaml_targets() -> list[_IPNetwork]:
    """Lee `authorized_targets.yaml` (formato: `targets: [{target: ..., label:
    ..., added: ...}, ...]`) -- solo el campo `target` de cada entrada importa
    acá, `label`/`added` son metadata para que el archivo sea auditable a
    simple vista, no se usan en la validación. Archivo ausente = ninguna
    ampliación de scope, NO un error (instalación nueva sin el archivo
    todavía creado sigue funcionando con el scope default). Una entrada
    individual mal formada se ignora (mismo criterio que
    `_parse_env_targets`) -- no tira abajo el archivo entero por un typo."""
    path = Path(settings.authorized_targets_path)
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return []  # YAML roto -- se trata como "sin ampliaciones", nunca como scope abierto por error de parseo

    networks: list[_IPNetwork] = []
    for entry in data.get("targets", []) or []:
        raw = entry.get("target") if isinstance(entry, dict) else None
        if not raw:
            continue
        try:
            networks.append(ipaddress.ip_network(str(raw).strip(), strict=False))
        except ValueError:
            continue
    return networks


def _parse_env_targets() -> list[_IPNetwork]:
    networks: list[_IPNetwork] = []
    for raw in settings.nmap_authorized_targets.split(","):
        raw = raw.strip()
        if not raw:
            continue
        try:
            networks.append(ipaddress.ip_network(raw, strict=False))
        except ValueError:
            continue  # entrada mal formada en la whitelist -- se ignora, no se rechaza el scan entero por eso
    return networks


def _parse_authorized_targets() -> list[_IPNetwork]:
    return [*_parse_yaml_targets(), *_parse_env_targets()]


def _resolve_to_network(target: str) -> tuple[_IPNetwork, str | None]:
    """Convierte `target` (IP suelta, CIDR, o hostname) a un `ip_network` --
    para un hostname, resuelve primero (nmap podría resolverlo él mismo, pero
    entonces el guardrail estaría validando el string crudo pedido, no la IP
    real a la que apunta: un hostname que resuelve a una IP pública tiene que
    rechazarse igual que si se hubiera pasado esa IP directo). Lanza
    `TargetNotAuthorizedError` si no es una IP/CIDR válida NI un hostname
    resoluble -- sintaxis de nmap más exóticas (rangos con guión tipo
    '10.0.0.1-50', wildcards '10.0.0.*', varios targets separados por
    espacio) no están soportadas por este guardrail a propósito: mejor
    rechazar de entrada que intentar parsear de más y dejar pasar algo mal
    entendido.

    Devuelve `(network, resolved_ip)` -- `resolved_ip` es `None` si
    `target` YA era una IP/CIDR literal (nunca hubo resolución DNS de por
    medio, nada que "pinnear"), o el string de la IP real si `target` era
    un hostname -- ver `resolve_and_authorize` para por qué esto importa
    (bug real de DNS rebinding arreglado 2026-08-13: el caller tiene que
    usar esta IP resuelta para la acción real, no volver a resolver el
    hostname original por su cuenta).

    Bug real encontrado en una segunda ronda de testing adversarial contra
    el gate (2026-08-13, "intentos creativos de evadirlo"): un target con
    un byte nulo embebido tiraba un `TypeError` crudo (no `ValueError`) de
    `socket.gethostbyname`, y un hostname absurdamente largo tiraba un
    `UnicodeError` ("label empty or too long") -- ninguno de los dos es un
    bypass real (ambos casos se rechazan igual), PERO como
    `resolve_and_authorize` documenta que SIEMPRE lanza
    `TargetNotAuthorizedError` para cualquier target inválido, un tipo de
    excepción distinto se escapaba de los `except TargetNotAuthorizedError`
    puntuales en nmap_scan/phone_nmap_scan/sqlmap_scan -- el intento
    rechazado nunca quedaba auditado en el log (gap real de trazabilidad,
    no de autorización: nada se llegaba a escanear, pero el intento
    tampoco quedaba registrado). Se normaliza acá, en el único punto de
    entrada real, para que NINGÚN tipo de excepción de resolución se
    escape sin pasar por `TargetNotAuthorizedError`."""
    candidate = target.strip()
    try:
        return ipaddress.ip_network(candidate, strict=False), None
    except ValueError:
        pass

    try:
        resolved_ip = socket.gethostbyname(candidate)
    except (socket.gaierror, UnicodeError, TypeError, OSError) as exc:
        raise TargetNotAuthorizedError(
            f"Target '{target}' no es una IP/CIDR válida ni un hostname resoluble ({exc}). "
            "Sintaxis tipo rangos con guión ('10.0.0.1-50') o wildcards ('10.0.0.*') no están "
            "soportadas -- usá una IP, un hostname simple, o un CIDR (ej. '192.168.1.0/24')."
        ) from exc
    return ipaddress.ip_network(resolved_ip), resolved_ip


def resolve_and_authorize(target: str) -> str:
    """Valida `target` (IP, CIDR, o hostname) contra el scope permitido
    ANTES de correr CUALQUIER tool de pentesting activo -- función
    compartida entre nmap_scan/phone_nmap_scan y todas las tools nuevas
    (sqlmap/tshark/metasploit/zap/nessus). Lanza `TargetNotAuthorizedError`
    si no está autorizado.

    Bug real de seguridad encontrado y arreglado 2026-08-13 (día de testing
    adversarial dedicado, prioridad #1 del día): esta función devolvía el
    `target` ORIGINAL sin modificar, y las 4 tools que la llaman
    DESCARTABAN el valor de retorno -- confirmaban que el hostname
    resolvía a algo autorizado en ESTE momento, pero después usaban el
    STRING original (no la IP ya validada) para la acción real, que la
    tool de turno (nmap/sqlmap/tshark) vuelve a resolver POR SU CUENTA al
    ejecutar. Con un hostname de TTL corto controlado por un atacante
    (DNS rebinding: primera resolución apunta a una IP privada, la
    resolución real momentos después apunta a algo público), el gate
    autorizaba algo que después terminaba actuando contra una IP distinta
    -- SSRF vía DNS rebinding, clase de vulnerabilidad conocida. Confirmado
    explotable con un mock de DNS que devuelve IPs distintas en llamadas
    sucesivas, no solo una preocupación teórica.

    Fix real: esta función ahora devuelve la IP YA RESUELTA (no el hostname
    original) -- las tools tienen que usar ESE valor para la acción real,
    nunca volver a resolver el string original por su cuenta. Para un
    target que ya era una IP/CIDR literal, devuelve el mismo string
    normalizado (nunca hubo ventana de rebinding ahí, no hay resolución de
    por medio).

    Un CIDR se valida COMPLETO (subred entera dentro de un rango permitido),
    no solo la primera IP -- si no, un CIDR mucho más ancho de lo que parece
    a simple vista (ej. pedir escanear "192.168.1.0/24" pero escribir por
    error "192.168.0.0/16") podría colar una porción fuera de scope."""
    network, resolved_ip = _resolve_to_network(target)

    allowed = [*_DEFAULT_SCOPE_RANGES, *_parse_authorized_targets()]
    is_authorized = any(
        network.version == allowed_net.version and network.subnet_of(allowed_net)
        for allowed_net in allowed
    )
    if not is_authorized:
        raise TargetNotAuthorizedError(
            f"Target '{target}' (resuelve a {network}) está fuera del scope autorizado por "
            "default (privado RFC1918, loopback, o el rango fijo de Tailscale) y no está en "
            "authorized_targets.yaml ni en NMAP_AUTHORIZED_TARGETS. Actuar contra una IP/dominio "
            "público sin autorización explícita del dueño puede ser ilegal (Ley 26.388 en "
            "Argentina, leyes de acceso no autorizado / computer fraud en la mayoría de países) -- "
            "si este target es tuyo o tenés autorización explícita, el USUARIO (no el LLM) tiene "
            "que agregarlo a mano a authorized_targets.yaml (ver authorized_targets.yaml.example). "
            "Ninguna tool ni ningún mensaje de chat puede ampliar este scope -- 'el usuario dijo "
            "que sí' no es un camino de autorización válido."
        )
    # `resolved_ip` es None si `target` ya era una IP/CIDR literal (se
    # devuelve tal cual, no hubo resolución) -- si era un hostname, se
    # devuelve la IP YA RESUELTA Y VALIDADA, nunca el hostname original
    # (ver docstring: cerrar la ventana de DNS rebinding).
    return resolved_ip if resolved_ip is not None else target
