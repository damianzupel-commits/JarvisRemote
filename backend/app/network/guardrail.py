"""Guardrail de scope para `nmap_scan` (ver `app/tools/network_scan.py`) --
a diferencia del resto del pipeline de seguridad de Jarvis (SAST/SCA puro,
solo lee código/manifiestos en disco), nmap escanea sistemas de RED reales.
Escanear una IP/dominio que no es tuyo y sin autorización explícita del dueño
puede ser ilegal (leyes de acceso no autorizado / computer fraud en la
mayoría de países) -- por eso esto es un guardrail TÉCNICO real (rechazo duro
antes de ejecutar nada), no solo una instrucción de system prompt: ni la tool
ni el LLM pueden bypassearlo con ningún argumento de la tool call. La única
forma de ampliar el scope es que el USUARIO edite `NMAP_AUTHORIZED_TARGETS` a
mano en `backend/.env` -- ver `config.py`.

Scope permitido por default (sin tocar ninguna config):
  - RFC 1918 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  - loopback (127.0.0.0/8)
  - el rango fijo de Tailscale (100.64.0.0/10) -- reusado de
    `network_info.TAILSCALE_RANGE` en vez de redefinido, para que las dos
    nociones de "es Tailscale" del proyecto no puedan divergir.

Cualquier otro target (IP pública, o un hostname que resuelva a una) se
rechaza salvo que caiga dentro de `settings.nmap_authorized_targets`.
"""

from __future__ import annotations

import ipaddress
import socket

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
    """El target no cae en el scope privado/loopback/Tailscale por default ni
    en la whitelist explícita de NMAP_AUTHORIZED_TARGETS."""


def _parse_authorized_targets() -> list[_IPNetwork]:
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


def _resolve_to_network(target: str) -> _IPNetwork:
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
    entendido."""
    candidate = target.strip()
    try:
        return ipaddress.ip_network(candidate, strict=False)
    except ValueError:
        pass

    try:
        resolved_ip = socket.gethostbyname(candidate)
    except socket.gaierror as exc:
        raise TargetNotAuthorizedError(
            f"Target '{target}' no es una IP/CIDR válida ni un hostname resoluble ({exc}). "
            "Sintaxis de nmap tipo rangos con guión ('10.0.0.1-50') o wildcards ('10.0.0.*') "
            "no están soportadas -- usá una IP, un hostname simple, o un CIDR (ej. '192.168.1.0/24')."
        ) from exc
    return ipaddress.ip_network(resolved_ip)


def resolve_and_authorize(target: str) -> str:
    """Valida `target` contra el scope permitido ANTES de correr nmap.
    Devuelve `target` tal cual (sin modificar -- nmap re-resuelve/parsea por
    su cuenta) si está autorizado; lanza `TargetNotAuthorizedError` si no.

    Un CIDR se valida COMPLETO (subred entera dentro de un rango permitido),
    no solo la primera IP -- si no, un CIDR mucho más ancho de lo que parece
    a simple vista (ej. pedir escanear "192.168.1.0/24" pero escribir por
    error "192.168.0.0/16") podría colar una porción fuera de scope."""
    network = _resolve_to_network(target)

    allowed = [*_DEFAULT_SCOPE_RANGES, *_parse_authorized_targets()]
    is_authorized = any(
        network.version == allowed_net.version and network.subnet_of(allowed_net)
        for allowed_net in allowed
    )
    if not is_authorized:
        raise TargetNotAuthorizedError(
            f"Target '{target}' (resuelve a {network}) está fuera del scope autorizado por "
            "default (privado RFC1918, loopback, o el rango fijo de Tailscale) y no está en "
            "NMAP_AUTHORIZED_TARGETS. Escanear una IP/dominio público sin autorización explícita "
            "del dueño puede ser ilegal (leyes de acceso no autorizado / computer fraud en la "
            "mayoría de países) -- si esta IP es tuya o tenés autorización explícita para "
            "escanearla, el USUARIO (no el LLM) tiene que agregarla a mano a "
            "NMAP_AUTHORIZED_TARGETS en backend/.env. La tool no puede ampliar su propio scope."
        )
    return target
