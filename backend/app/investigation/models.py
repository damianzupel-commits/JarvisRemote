"""Modelo de entidades tipado del módulo de investigación (spec sección 1).

Diseño: un único `Node`/`Edge` como envoltorio de almacenamiento uniforme
(simplifica la persistencia JSONL y los algoritmos de grafo, que no
necesitan conocer los campos específicos de cada tipo), pero la creación
SIEMPRE pasa por una función `make_*` con firma tipada por tipo de entidad --
así el "schema tipado" que pide la spec se cumple en el punto de
construcción (typo en un campo requerido = error inmediato), no confiando en
que quien llama arme el dict a mano correctamente.

IDs determinísticos donde hay una clave natural real (Archivo -> su propio
sha256, Cuenta -> plataforma+handle, Host -> ip/dominio): esto es lo que
resuelve la decisión de Damian sobre reingesta -- el mismo archivo/cuenta/
host mencionado en dos artefactos distintos (o el mismo artefacto recargado)
resuelve SIEMPRE al mismo id de nodo, nunca crea un duplicado. Persona/
Organización/Evento/Transacción no tienen una clave natural confiable entre
fuentes -- nacen con id aleatorio, y la deduplicación de personas es
DELIBERADAMENTE manual/asistida vía la arista `mismo_que` (spec sección 3),
nunca automática por nombre (dos personas reales pueden compartir nombre;
fusionar por texto sería exactamente el tipo de inferencia no verificada que
la spec prohíbe)."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class NodeType(str, Enum):
    PERSONA = "Persona"
    CUENTA = "Cuenta"
    DISPOSITIVO = "Dispositivo"
    HOST = "Host"
    ARCHIVO = "Archivo"
    TRANSACCION = "Transacción"
    EVENTO = "Evento"
    ORGANIZACION = "Organización"


class EdgeType(str, Enum):
    USA = "usa"
    CONTROLA = "controla"
    COMUNICA_CON = "comunica_con"
    TRANSFIERE_A = "transfiere_a"
    APARECE_EN = "aparece_en"
    CO_OCURRE_CON = "co-ocurre_con"
    MISMO_QUE = "mismo_que"


class DerivadaPor(str, Enum):
    PARSER = "parser"
    MODELO = "modelo"
    MANUAL = "manual"


# Campos requeridos por tipo de nodo (tabla de la spec, sección 1) -- usado
# por `_validate_campos` para que un `make_*` con un campo faltante falle
# ahí mismo, no silenciosamente más adelante cuando algo intente leerlo.
REQUIRED_NODE_FIELDS: dict[NodeType, frozenset[str]] = {
    NodeType.PERSONA: frozenset({"etiqueta", "alias", "confianza"}),
    NodeType.CUENTA: frozenset({"plataforma", "handle", "fecha_alta"}),
    NodeType.DISPOSITIVO: frozenset({"tipo_dispositivo", "identificadores"}),
    NodeType.HOST: frozenset({"ip_o_dominio", "asn", "geolocalizacion_declarada"}),
    NodeType.ARCHIVO: frozenset({"nombre", "sha256", "tamano", "mime"}),
    NodeType.TRANSACCION: frozenset({"tipo_transaccion", "monto", "timestamp", "contraparte"}),
    NodeType.EVENTO: frozenset({"timestamp_utc", "descripcion", "fuente"}),
    NodeType.ORGANIZACION: frozenset({"nombre", "identificadores"}),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_confianza(value: float, label: str) -> None:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{label} debe estar en el rango [0, 1], recibido {value!r}")


def _validate_campos(tipo: NodeType, campos: dict[str, Any]) -> None:
    required = REQUIRED_NODE_FIELDS[tipo]
    missing = required - campos.keys()
    if missing:
        raise ValueError(f"Faltan campos requeridos para {tipo.value}: {sorted(missing)}")


def deterministic_node_id(tipo: NodeType, natural_key: str) -> str:
    """Mismo (tipo, natural_key) -> SIEMPRE el mismo id -- ver docstring del
    módulo. `natural_key` tiene que ser algo que de verdad identifique a la
    entidad de forma estable entre fuentes (el sha256 del archivo, no su
    nombre; plataforma+handle de una cuenta, no un display name que puede
    cambiar)."""
    digest = hashlib.sha256(f"{tipo.value}:{natural_key}".encode("utf-8")).hexdigest()[:32]
    return f"{tipo.value.lower()}-{digest}"


def _random_node_id(tipo: NodeType) -> str:
    return f"{tipo.value.lower()}-{uuid.uuid4().hex}"


@dataclass
class Node:
    id: str
    tipo: NodeType
    campos: dict[str, Any]
    created_at: str = field(default_factory=_now)
    retracted: bool = False
    retracted_reason: str | None = None
    retracted_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo.value,
            "campos": self.campos,
            "created_at": self.created_at,
            "retracted": self.retracted,
            "retracted_reason": self.retracted_reason,
            "retracted_at": self.retracted_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "Node":
        return Node(
            id=data["id"],
            tipo=NodeType(data["tipo"]),
            campos=data["campos"],
            created_at=data.get("created_at", _now()),
            retracted=data.get("retracted", False),
            retracted_reason=data.get("retracted_reason"),
            retracted_at=data.get("retracted_at"),
        )

    def retract(self, reason: str, at: str | None = None) -> None:
        """Nunca se borra un nodo de verdad (spec sección 6) -- esto marca
        la retracción sin tocar `campos` ni el resto del historial.

        `at` opcional: quien llama en el momento REAL de la retracción
        (case_store.retract_node) no lo pasa, así que usa "ahora". Pero
        `case_store.rebuild_from_log` SÍ lo pasa (el timestamp real de la
        entrada del log) -- si no, cada reconstrucción generaría un
        `retracted_at` nuevo (el momento de la reconstrucción, no el de la
        retracción real), rompiendo la promesa de que reconstruir desde el
        log da EXACTAMENTE el mismo estado que el materializado (bug real
        encontrado por el test de reconstrucción de case_store)."""
        self.retracted = True
        self.retracted_reason = reason
        self.retracted_at = at or _now()


@dataclass
class Edge:
    id: str
    tipo: EdgeType
    origen: str  # Node.id
    destino: str  # Node.id
    timestamp: str
    artefacto_origen: str  # id del Node tipo Archivo del que salió esta arista
    confianza: float
    derivada_por: DerivadaPor
    created_at: str = field(default_factory=_now)
    retracted: bool = False
    retracted_reason: str | None = None
    retracted_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tipo": self.tipo.value,
            "origen": self.origen,
            "destino": self.destino,
            "timestamp": self.timestamp,
            "artefacto_origen": self.artefacto_origen,
            "confianza": self.confianza,
            "derivada_por": self.derivada_por.value,
            "created_at": self.created_at,
            "retracted": self.retracted,
            "retracted_reason": self.retracted_reason,
            "retracted_at": self.retracted_at,
        }

    @staticmethod
    def from_dict(data: dict) -> "Edge":
        return Edge(
            id=data["id"],
            tipo=EdgeType(data["tipo"]),
            origen=data["origen"],
            destino=data["destino"],
            timestamp=data["timestamp"],
            artefacto_origen=data["artefacto_origen"],
            confianza=data["confianza"],
            derivada_por=DerivadaPor(data["derivada_por"]),
            created_at=data.get("created_at", _now()),
            retracted=data.get("retracted", False),
            retracted_reason=data.get("retracted_reason"),
            retracted_at=data.get("retracted_at"),
        )

    def retract(self, reason: str, at: str | None = None) -> None:
        """Ver Node.retract() -- mismo motivo real para el parámetro `at`."""
        self.retracted = True
        self.retracted_reason = reason
        self.retracted_at = at or _now()


def make_persona(*, etiqueta: str, confianza: float, alias: list[str] | None = None, node_id: str | None = None) -> Node:
    """`confianza` acá es UN solo número combinado (decisión de Damian,
    2026-08-12): mide a la vez "existe esta entidad como algo distinguible"
    y "el/los alias listados le pertenecen de verdad" -- no dos ejes
    separados. Sin clave natural confiable entre fuentes -- id aleatorio por
    default; la deduplicación real pasa por `mismo_que` (ver case_store.py),
    nunca por matchear el nombre acá."""
    _validate_confianza(confianza, "confianza de Persona")
    campos = {"etiqueta": etiqueta, "alias": alias or [], "confianza": confianza}
    _validate_campos(NodeType.PERSONA, campos)
    return Node(id=node_id or _random_node_id(NodeType.PERSONA), tipo=NodeType.PERSONA, campos=campos)


def make_cuenta(*, plataforma: str, handle: str, fecha_alta: str | None = None) -> Node:
    campos = {"plataforma": plataforma, "handle": handle, "fecha_alta": fecha_alta}
    _validate_campos(NodeType.CUENTA, campos)
    node_id = deterministic_node_id(NodeType.CUENTA, f"{plataforma}:{handle}")
    return Node(id=node_id, tipo=NodeType.CUENTA, campos=campos)


def make_dispositivo(*, tipo_dispositivo: str, identificadores: list[str], node_id: str | None = None) -> Node:
    campos = {"tipo_dispositivo": tipo_dispositivo, "identificadores": identificadores}
    _validate_campos(NodeType.DISPOSITIVO, campos)
    if node_id is None:
        natural_key = identificadores[0] if identificadores else None
        node_id = (
            deterministic_node_id(NodeType.DISPOSITIVO, natural_key)
            if natural_key
            else _random_node_id(NodeType.DISPOSITIVO)
        )
    return Node(id=node_id, tipo=NodeType.DISPOSITIVO, campos=campos)


def make_host(*, ip_o_dominio: str, asn: str | None = None, geolocalizacion_declarada: str | None = None) -> Node:
    campos = {"ip_o_dominio": ip_o_dominio, "asn": asn, "geolocalizacion_declarada": geolocalizacion_declarada}
    _validate_campos(NodeType.HOST, campos)
    node_id = deterministic_node_id(NodeType.HOST, ip_o_dominio)
    return Node(id=node_id, tipo=NodeType.HOST, campos=campos)


def make_archivo(*, nombre: str, sha256: str, tamano: int, mime: str) -> Node:
    """El id SIEMPRE es determinístico por sha256 -- es la clave natural más
    fuerte de todo el schema (dos archivos con el mismo hash son, por
    definición, el mismo contenido byte a byte)."""
    campos = {"nombre": nombre, "sha256": sha256, "tamano": tamano, "mime": mime}
    _validate_campos(NodeType.ARCHIVO, campos)
    return Node(id=deterministic_node_id(NodeType.ARCHIVO, sha256), tipo=NodeType.ARCHIVO, campos=campos)


def make_transaccion(
    *, tipo_transaccion: str, monto: float, timestamp: str, contraparte: str | None = None, node_id: str | None = None
) -> Node:
    campos = {"tipo_transaccion": tipo_transaccion, "monto": monto, "timestamp": timestamp, "contraparte": contraparte}
    _validate_campos(NodeType.TRANSACCION, campos)
    return Node(id=node_id or _random_node_id(NodeType.TRANSACCION), tipo=NodeType.TRANSACCION, campos=campos)


def make_evento(
    *, timestamp_utc: str, descripcion: str, fuente: str, node_id: str | None = None
) -> Node:
    campos = {"timestamp_utc": timestamp_utc, "descripcion": descripcion, "fuente": fuente}
    _validate_campos(NodeType.EVENTO, campos)
    return Node(id=node_id or _random_node_id(NodeType.EVENTO), tipo=NodeType.EVENTO, campos=campos)


def make_organizacion(*, nombre: str, identificadores: list[str] | None = None, node_id: str | None = None) -> Node:
    campos = {"nombre": nombre, "identificadores": identificadores or []}
    _validate_campos(NodeType.ORGANIZACION, campos)
    return Node(id=node_id or _random_node_id(NodeType.ORGANIZACION), tipo=NodeType.ORGANIZACION, campos=campos)


def make_edge(
    *,
    tipo: EdgeType,
    origen: str,
    destino: str,
    artefacto_origen: str,
    confianza: float,
    derivada_por: DerivadaPor,
    timestamp: str | None = None,
) -> Edge:
    _validate_confianza(confianza, f"confianza de arista '{tipo.value}'")
    return Edge(
        id=uuid.uuid4().hex,
        tipo=tipo,
        origen=origen,
        destino=destino,
        timestamp=timestamp or _now(),
        artefacto_origen=artefacto_origen,
        confianza=confianza,
        derivada_por=derivada_por,
    )
