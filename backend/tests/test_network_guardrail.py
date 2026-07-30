"""Tests del guardrail de scope de nmap_scan (app/network/guardrail.py) -- el
límite de seguridad más importante de esta tool: confirma que rangos
privados/loopback/Tailscale pasan, que CUALQUIER IP pública se rechaza por
default, y que la whitelist explícita (NMAP_AUTHORIZED_TARGETS) es la única
forma de ampliar el scope -- nunca un argumento de la tool call."""

import pytest

from app.config import settings
from app.network import guardrail


@pytest.mark.parametrize(
    "target",
    [
        "10.0.0.5",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.1.1",
        "192.168.1.0/24",
        "127.0.0.1",
        "localhost",
        "100.64.0.1",  # rango fijo de Tailscale
        "100.127.255.255",  # extremo superior de 100.64.0.0/10
    ],
)
def test_private_and_tailscale_targets_are_authorized(target):
    assert guardrail.resolve_and_authorize(target) == target


@pytest.mark.parametrize(
    "target",
    [
        "8.8.8.8",  # Google DNS -- IP pública real, no es de Damian
        "1.1.1.1",  # Cloudflare DNS
        "203.0.113.10",  # TEST-NET-3, documentación pero pública igual
        "0.0.0.0/0",  # CIDR que cubre TODO internet -- ninguna red permitida es superset de esto
        "172.0.0.0/8",  # se superpone con 172.16.0.0/12 pero es un /8 mucho más ancho, no un subset
        "100.63.255.255",  # justo AFUERA del rango de Tailscale (un bit antes de 100.64.0.0/10)
        "100.128.0.0",  # justo AFUERA del rango de Tailscale (un bit después)
    ],
)
def test_public_targets_are_rejected_by_default(target):
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize(target)


def test_hostname_resolving_to_public_ip_is_rejected(monkeypatch):
    """Un hostname (no una IP directa) que resuelve a algo público tiene que
    rechazarse igual que si se hubiera pasado esa IP pública directo -- el
    guardrail no puede confiar en el string crudo, tiene que resolver primero."""
    monkeypatch.setattr(guardrail.socket, "gethostbyname", lambda name: "203.0.113.50")
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("some-public-host.example.com")


def test_hostname_resolving_to_private_ip_is_authorized(monkeypatch):
    monkeypatch.setattr(guardrail.socket, "gethostbyname", lambda name: "192.168.1.50")
    assert guardrail.resolve_and_authorize("my-nas.local") == "my-nas.local"


def test_unresolvable_hostname_is_rejected(monkeypatch):
    import socket as real_socket

    def raise_gaierror(name):
        raise real_socket.gaierror("no address associated with hostname")

    monkeypatch.setattr(guardrail.socket, "gethostbyname", raise_gaierror)
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("this-does-not-resolve.invalid")


@pytest.mark.parametrize("target", ["10.0.0.1-50", "10.0.0.*", "10.0.0.1 10.0.0.2"])
def test_exotic_nmap_target_syntax_is_rejected_not_parsed(target, monkeypatch):
    """Rangos con guión, wildcards, o varios targets en un string no están
    soportados por el guardrail a propósito -- mejor rechazar de entrada que
    intentar parsear de más y dejar pasar algo mal entendido. Como ninguno de
    estos strings es una IP/CIDR válida, cae en la rama de resolución de
    hostname -- se fuerza a que esa resolución falle (no son hostnames reales)
    para no depender de DNS real en el test."""
    import socket as real_socket

    def raise_gaierror(name):
        raise real_socket.gaierror("not a real hostname")

    monkeypatch.setattr(guardrail.socket, "gethostbyname", raise_gaierror)
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize(target)


def test_public_ip_authorized_via_explicit_whitelist(monkeypatch):
    monkeypatch.setattr(settings, "nmap_authorized_targets", "203.0.113.10,203.0.113.0/24")
    assert guardrail.resolve_and_authorize("203.0.113.10") == "203.0.113.10"
    assert guardrail.resolve_and_authorize("203.0.113.200") == "203.0.113.200"  # dentro del /24 whitelisteado


def test_public_ip_not_in_whitelist_still_rejected(monkeypatch):
    monkeypatch.setattr(settings, "nmap_authorized_targets", "203.0.113.10")
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("8.8.8.8")


def test_malformed_whitelist_entries_are_ignored_not_fatal(monkeypatch):
    """Una entrada mal escrita en NMAP_AUTHORIZED_TARGETS no debe romper el
    parseo de las demás -- se ignora esa entrada puntual, no se agranda el
    scope por accidente ni se cae la validación entera."""
    monkeypatch.setattr(settings, "nmap_authorized_targets", "not-an-ip, 203.0.113.10")
    assert guardrail.resolve_and_authorize("203.0.113.10") == "203.0.113.10"
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("8.8.8.8")


def test_empty_whitelist_authorizes_nothing_extra(monkeypatch):
    monkeypatch.setattr(settings, "nmap_authorized_targets", "")
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("8.8.8.8")
