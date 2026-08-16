"""Gestión de la clave de firma del log de investigación (spec sección 6 --
decisión de Damian, 2026-08-12: "vamos por todo de una", firma criptográfica
REAL con par de claves, no solo encadenamiento por hash).

## Decisión de diseño (para que Damian la revise, tal como pidió)

**Algoritmo**: Ed25519 (`cryptography.hazmat.primitives.asymmetric.ed25519`).
Firmas rápidas, claves de 32 bytes, estándar moderno con soporte real en la
librería que ya está instalada en el proyecto -- no hay ninguna ventaja real
de RSA acá (más lento, claves mucho más grandes) para un caso de un solo
firmante local.

**Dónde vive la clave privada y cómo se protege**: en disco, cifrada con
DPAPI (Windows Data Protection API, vía `win32crypt` -- YA es una
dependencia real del proyecto, `pywin32`, usada hoy para otras cosas). DPAPI
ata el cifrado a la cuenta de usuario de Windows actual -- nadie puede
desencriptar el archivo copiándolo a otra máquina o leyéndolo con otra
cuenta de Windows, y Jarvis no tiene que pedir ninguna contraseña en cada
arranque (el login de Windows ya es el factor de desbloqueo real). Es un
nivel de protección bastante por encima de cómo el resto del proyecto guarda
sus secretos hoy (API_KEY/GOOGLE_AI_API_KEY viven en texto plano en
`backend/.env`) -- elegido a propósito para ESTA clave puntual porque firma
un registro que puede terminar siendo evidencia real, no solo autentica
contra un servicio externo.

**Alternativas consideradas y descartadas**: (a) clave en texto plano como
el resto de los secretos del proyecto -- descartada, es justo el nivel que
Damian pidió superar acá; (b) clave protegida con una passphrase que se
pide en cada arranque -- más portable entre máquinas, pero rompe el modelo
de "backend que arranca solo" que ya tiene todo el resto de Jarvis, y
agrega un punto de fricción/olvido real; (c) HSM/TPM -- viable a futuro si
hace falta, pero es una dependencia de hardware que esta PC no tiene
confirmada, se puede migrar después sin tocar el formato del log (la firma
en cada entrada es independiente de DÓNDE vive la clave).

**Limitación real, dicha explícitamente**: DPAPI ata la clave a ESTA cuenta
de Windows en ESTA máquina. Si el disco se mueve a otra PC o se reinstala
Windows, la clave privada NO se puede recuperar del blob cifrado -- hace
falta un backup aparte de la clave (recomendado: exportar
`signing_key.pub` + guardar una copia del blob DPAPI en un lugar seguro
fuera de esta PC). Firmas YA hechas siguen siendo verificables para siempre
con la clave pública (que no está protegida, es de lectura libre) aunque se
pierda la privada -- lo que se pierde es la capacidad de agregar entradas
NUEVAS con continuidad de firma, no la verificación de las viejas.

La clave PÚBLICA nunca está cifrada -- se guarda en texto plano aparte, y es
lo que cualquiera (sin acceso a la privada) puede usar para verificar la
cadena completa de forma independiente. Separación real de "quién puede
escribir" vs. "quién puede confirmar que no se tocó nada".
"""

from __future__ import annotations

from pathlib import Path

import win32crypt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

_DPAPI_DESCRIPTION = "jarvis investigation module signing key"

_PRIVATE_KEY_FILENAME = "signing_key.dpapi"
_PUBLIC_KEY_FILENAME = "signing_key.pub"


def _private_key_path(keys_dir: Path) -> Path:
    return keys_dir / _PRIVATE_KEY_FILENAME


def _public_key_path(keys_dir: Path) -> Path:
    return keys_dir / _PUBLIC_KEY_FILENAME


def ensure_keypair(keys_dir: str | Path) -> None:
    """Genera el par de claves si todavía no existe -- idempotente, no
    regenera (y por lo tanto no invalida firmas viejas) si ya hay una."""
    keys_dir = Path(keys_dir)
    if _private_key_path(keys_dir).is_file():
        return

    keys_dir.mkdir(parents=True, exist_ok=True)
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    protected = win32crypt.CryptProtectData(private_raw, _DPAPI_DESCRIPTION, None, None, None, 0)
    _private_key_path(keys_dir).write_bytes(protected)

    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    _public_key_path(keys_dir).write_bytes(public_raw)


def load_private_key(keys_dir: str | Path) -> ed25519.Ed25519PrivateKey:
    keys_dir = Path(keys_dir)
    path = _private_key_path(keys_dir)
    if not path.is_file():
        raise FileNotFoundError(
            f"No hay clave de firma en '{keys_dir}' -- llamar ensure_keypair() primero."
        )
    protected = path.read_bytes()
    _description, raw = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def load_public_key(keys_dir: str | Path) -> ed25519.Ed25519PublicKey:
    keys_dir = Path(keys_dir)
    path = _public_key_path(keys_dir)
    if not path.is_file():
        raise FileNotFoundError(
            f"No hay clave pública en '{keys_dir}' -- llamar ensure_keypair() primero."
        )
    return ed25519.Ed25519PublicKey.from_public_bytes(path.read_bytes())


def sign(private_key: ed25519.Ed25519PrivateKey, data: bytes) -> str:
    """Devuelve la firma en hex (más fácil de meter en un JSON de log que
    bytes crudos)."""
    return private_key.sign(data).hex()


def verify(public_key: ed25519.Ed25519PublicKey, data: bytes, signature_hex: str) -> bool:
    try:
        public_key.verify(bytes.fromhex(signature_hex), data)
        return True
    except InvalidSignature:
        return False
