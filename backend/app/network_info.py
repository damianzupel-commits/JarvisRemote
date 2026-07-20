"""Detecta las IPs locales de la PC y las clasifica para que el celular pueda
preferir una conexión directa (hotspot WiFi de la PC o LAN compartida) sobre
Tailscale cuando ambas estén disponibles.

El backend ya escucha en 0.0.0.0 (ver `config.Settings.host`), así que acepta
conexiones por cualquier interfaz simultáneamente — no hay nada que "preferir"
del lado del bind. La preferencia la aplica el celular al elegir a qué URL
conectarse primero; este módulo solo le da la lista de candidatos ordenada
(directo primero, Tailscale como fallback) vía `/api/health`.
"""

import ipaddress
import socket

_TAILSCALE_RANGE = ipaddress.ip_network("100.64.0.0/10")
_WINDOWS_HOTSPOT_RANGE = ipaddress.ip_network("192.168.137.0/24")

# Directo (hotspot o LAN compartida) antes que Tailscale: si el celular está
# en la misma red que la PC conviene la ruta corta en vez de salir por la VPN.
_TYPE_PRIORITY = {"hotspot": 0, "lan": 1, "tailscale": 2}


def _classify(ip: str) -> str | None:
    addr = ipaddress.ip_address(ip)
    if addr.is_loopback or addr.is_link_local:
        return None
    if addr in _TAILSCALE_RANGE:
        return "tailscale"
    if addr in _WINDOWS_HOTSPOT_RANGE:
        return "hotspot"
    if addr.is_private:
        return "lan"
    return None  # IP pública: nunca se ofrece como candidato (nada expuesto a internet)


def _local_ipv4_addresses() -> list[str]:
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except socket.gaierror:
        return []
    seen: set[str] = set()
    ips: list[str] = []
    for info in infos:
        ip = info[4][0]
        if ip not in seen:
            seen.add(ip)
            ips.append(ip)
    return ips


def network_candidates(port: int) -> list[dict[str, str]]:
    """Direcciones donde el backend es alcanzable ahora mismo, ordenadas de
    conexión directa (hotspot/LAN) a Tailscale (fallback)."""
    candidates = []
    for ip in _local_ipv4_addresses():
        kind = _classify(ip)
        if kind is None:
            continue
        candidates.append({"ip": ip, "type": kind, "url": f"http://{ip}:{port}"})
    candidates.sort(key=lambda c: _TYPE_PRIORITY.get(c["type"], 9))
    return candidates
