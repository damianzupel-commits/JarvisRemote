"""Tests del guardrail de scope compartido por TODAS las tools de
pentesting activo (app/network/guardrail.py) -- el límite de seguridad más
importante de todas esas tools: confirma que rangos privados/loopback/
Tailscale pasan, que CUALQUIER IP pública se rechaza por default, y que
authorized_targets.yaml/NMAP_AUTHORIZED_TARGETS son la ÚNICA forma de
ampliar el scope -- nunca un argumento de la tool call."""

import pytest

from app.config import settings
from app.network import guardrail


@pytest.fixture(autouse=True)
def _isolated_yaml_path(tmp_path, monkeypatch):
    """SIEMPRE apunta a un archivo que no existe por default -- si no, estos
    tests dependerían del `authorized_targets.yaml` REAL de quien los corra
    (no determinístico, y potencialmente exponiendo su config personal en
    resultados de test)."""
    monkeypatch.setattr(settings, "authorized_targets_path", str(tmp_path / "no-existe.yaml"))


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
        "100.64.0.1",  # rango fijo de Tailscale
        "100.127.255.255",  # extremo superior de 100.64.0.0/10
    ],
)
def test_private_and_tailscale_ip_literals_are_authorized_and_returned_unchanged(target):
    """IP/CIDR literales -- nunca hubo resolución DNS de por medio, así que
    el gate devuelve el mismo valor tal cual (nada que pinnear)."""
    assert guardrail.resolve_and_authorize(target) == target


def test_localhost_hostname_is_authorized_and_returns_the_resolved_ip():
    """Bug real de DNS rebinding arreglado 2026-08-13 (ver docstring de
    resolve_and_authorize): un HOSTNAME (a diferencia de una IP literal)
    ahora devuelve la IP YA RESUELTA, no el string original -- el caller
    tiene que usar ese valor para la acción real, nunca volver a resolver
    el hostname por su cuenta (eso es exactamente la ventana de rebinding
    que este cambio cierra)."""
    assert guardrail.resolve_and_authorize("localhost") == "127.0.0.1"


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
    """Devuelve la IP resuelta, NO el hostname original -- ver
    test_localhost_hostname_is_authorized_and_returns_the_resolved_ip."""
    monkeypatch.setattr(guardrail.socket, "gethostbyname", lambda name: "192.168.1.50")
    assert guardrail.resolve_and_authorize("my-nas.local") == "192.168.1.50"


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


# --- authorized_targets.yaml (fuente única compartida, decisión de Damian 2026-08-13) ------

def _write_yaml(path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_public_ip_authorized_via_yaml_file(tmp_path, monkeypatch):
    yaml_path = tmp_path / "authorized_targets.yaml"
    _write_yaml(yaml_path, "targets:\n  - target: '203.0.113.10'\n    label: 'lab propio'\n    added: '2026-08-13'\n")
    monkeypatch.setattr(settings, "authorized_targets_path", str(yaml_path))

    assert guardrail.resolve_and_authorize("203.0.113.10") == "203.0.113.10"


def test_yaml_and_env_var_targets_are_both_honored(tmp_path, monkeypatch):
    """Retrocompatibilidad real: si Damian ya tenía NMAP_AUTHORIZED_TARGETS
    configurado, no se rompe cuando además existe el YAML -- los dos se
    combinan, ninguno reemplaza al otro."""
    yaml_path = tmp_path / "authorized_targets.yaml"
    _write_yaml(yaml_path, "targets:\n  - target: '203.0.113.10'\n")
    monkeypatch.setattr(settings, "authorized_targets_path", str(yaml_path))
    monkeypatch.setattr(settings, "nmap_authorized_targets", "198.51.100.20")

    assert guardrail.resolve_and_authorize("203.0.113.10") == "203.0.113.10"
    assert guardrail.resolve_and_authorize("198.51.100.20") == "198.51.100.20"


def test_missing_yaml_file_is_not_an_error(tmp_path, monkeypatch):
    """Instalación nueva sin el archivo creado todavía -- funciona con el
    scope default, no rompe nada (mismo criterio que un .env sin
    NMAP_AUTHORIZED_TARGETS)."""
    monkeypatch.setattr(settings, "authorized_targets_path", str(tmp_path / "no-existe.yaml"))
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("8.8.8.8")  # sigue rechazando lo público, sin romper


def test_malformed_yaml_is_treated_as_no_extra_targets_not_fatal(tmp_path, monkeypatch):
    yaml_path = tmp_path / "authorized_targets.yaml"
    _write_yaml(yaml_path, "esto: [no, es, yaml, valido: : :")
    monkeypatch.setattr(settings, "authorized_targets_path", str(yaml_path))

    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("8.8.8.8")  # el YAML roto NO abre el scope por error


def test_yaml_entry_missing_target_field_is_ignored_not_fatal(tmp_path, monkeypatch):
    yaml_path = tmp_path / "authorized_targets.yaml"
    _write_yaml(yaml_path, "targets:\n  - label: 'sin campo target, mal formada'\n  - target: '203.0.113.10'\n")
    monkeypatch.setattr(settings, "authorized_targets_path", str(yaml_path))

    assert guardrail.resolve_and_authorize("203.0.113.10") == "203.0.113.10"  # la entrada valida se lee igual


def test_empty_yaml_file_authorizes_nothing_extra(tmp_path, monkeypatch):
    yaml_path = tmp_path / "authorized_targets.yaml"
    _write_yaml(yaml_path, "")
    monkeypatch.setattr(settings, "authorized_targets_path", str(yaml_path))

    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("8.8.8.8")


def test_dns_rebinding_window_is_closed(monkeypatch):
    """Regresión explícita para el bug real de seguridad encontrado y
    arreglado 2026-08-13 (día de testing adversarial): un hostname con TTL
    corto que resuelve a una IP privada la PRIMERA vez (cuando el gate
    valida) y a una IP pública la SEGUNDA vez (cuando la tool downstream
    se conectaría de verdad, si volviera a resolver por su cuenta).
    Confirmado explotable ANTES del fix: el gate devolvía el hostname
    original, así que cualquier caller que lo usara para la acción real
    terminaría re-resolviendo y conectándose a la IP pública, sin volver a
    pasar por el gate. Este test prueba que el valor que el gate DEVUELVE
    ahora es la IP ya fijada -- un caller que use ESE valor (en vez de
    volver a resolver el hostname original) nunca ve la segunda IP."""
    calls = {"n": 0}

    def rebinding_dns(name):
        calls["n"] += 1
        return "192.168.1.50" if calls["n"] == 1 else "8.8.8.8"

    monkeypatch.setattr(guardrail.socket, "gethostbyname", rebinding_dns)

    result = guardrail.resolve_and_authorize("rebind-attacker.example.com")

    assert result == "192.168.1.50"  # la IP que el gate vio y autorizó -- NUNCA el hostname original
    assert calls["n"] == 1  # una sola resolución real -- el resultado ya está fijado, no hay una "segunda vuelta" que reabra la ventana


def test_yaml_target_does_not_need_to_be_reachable(tmp_path, monkeypatch):
    """Decisión de Damian 2026-08-13: los laboratorios (PyGoat/NodeGoat/etc.)
    se levantan bajo demanda -- la autorización de un target NO depende de
    que esté corriendo/alcanzable en este momento. Este test usa una IP
    documentacional (TEST-NET-3, RFC 5737) que casi seguro no responde a
    nada real, y confirma que el gate la autoriza igual -- el gate valida
    pertenencia a un rango, nunca conectividad."""
    yaml_path = tmp_path / "authorized_targets.yaml"
    _write_yaml(yaml_path, "targets:\n  - target: '203.0.113.99'\n    label: 'lab que hoy no esta corriendo'\n")
    monkeypatch.setattr(settings, "authorized_targets_path", str(yaml_path))

    assert guardrail.resolve_and_authorize("203.0.113.99") == "203.0.113.99"


# --- segunda ronda de testing adversarial contra el gate (2026-08-13) -----------------

@pytest.mark.parametrize(
    "target",
    [
        "134744072",  # 8.8.8.8 en notacion decimal entera
        "0x08080808",  # 8.8.8.8 en notacion hexadecimal
        "008.8.8.8",  # octeto con cero a la izquierda (ambiguo, CVE-2021-29921)
        "::ffff:8.8.8.8",  # IPv4 publica mapeada en IPv6
        " 8.8.8.8",  # espacio embebido antes
        "8.8.8.8 ",  # espacio embebido despues
        "GOOGLE.COM",  # mayusculas -- no debería ni importar, pero confirma que no hay atajo
        "google.com.",  # punto final de FQDN
        "8.0.0.0/8",  # CIDR publico amplio
    ],
)
def test_alternate_ip_notations_pointing_public_are_all_rejected(target, monkeypatch):
    """Ronda 2 de intentos de evasión del gate (2026-08-13): notaciones
    alternativas de IP (decimal, hex, octal con cero a la izquierda,
    IPv4-mapeada-en-IPv6) que algunos parsers de bajo nivel aceptan como
    atajos de `inet_aton` -- ninguna resultó ser un bypass real, todas se
    rechazan (Python's `ipaddress` + `socket.gethostbyname` de Windows no
    caen en ninguna de estas)."""
    monkeypatch.setattr(guardrail.socket, "gethostbyname", lambda name: (_ for _ in ()).throw(guardrail.socket.gaierror("no resuelve")))
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize(target)


def test_a_null_byte_in_the_target_raises_target_not_authorized_not_a_raw_type_error(monkeypatch):
    """Bug real encontrado en la ronda 2 de testing adversarial: un byte
    nulo embebido tiraba un TypeError crudo de socket.gethostbyname (no
    ValueError/gaierror) -- se ESCAPABA del contrato documentado de
    `resolve_and_authorize` ('siempre lanza TargetNotAuthorizedError'), lo
    que hacía que nmap_scan/sqlmap_scan NUNCA auditaran el intento
    rechazado (su except puntual no atrapaba TypeError)."""
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("127.0.0.1\x00google.com")


def test_an_absurdly_long_hostname_raises_target_not_authorized_not_a_raw_unicode_error(monkeypatch):
    """Mismo bug, otro tipo de excepción que se escapaba: un hostname de
    100k caracteres tiraba UnicodeError ('label empty or too long') crudo
    en vez de TargetNotAuthorizedError."""
    with pytest.raises(guardrail.TargetNotAuthorizedError):
        guardrail.resolve_and_authorize("a" * 100_000 + ".com")
