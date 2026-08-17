"""Override de contexto (vault + índice de embeddings) para perfiles
alternativos al vault de seguridad/código por default -- ver app/agent.py
(perfil de investigación científica, agregado 2026-08-12, ítem 4 de la cola
de esa sesión).

Usa `contextvars.ContextVar`, NO una variable global mutable, a propósito:
el backend es async y puede haber varias conversaciones/tool-calls
concurrentes (dos pestañas, el celular y la PC a la vez, etc.) -- una var
global mutable pisaría el vault activo de una conversación con el de otra
que arranca en el medio de la primera. Un ContextVar es por-tarea-de-asyncio:
cada `run_agent` corre en su propia tarea, así que el override que setea acá
nunca se cruza con el de otra conversación concurrente, sin necesidad de
pasar un parámetro `vault_path` a mano por cada función de vault.py/
embeddings.py (que hoy no lo tienen, y agregarlo a las ~8 funciones públicas
de esos dos módulos hubiera sido un refactor mucho más invasivo para el
mismo resultado)."""

from __future__ import annotations

import contextlib
import contextvars
from dataclasses import dataclass


@dataclass(frozen=True)
class VaultProfile:
    vault_path: str
    embeddings_path: str


_active_profile: contextvars.ContextVar["VaultProfile | None"] = contextvars.ContextVar(
    "active_vault_profile", default=None
)


@contextlib.contextmanager
def use_profile(profile: VaultProfile):
    token = _active_profile.set(profile)
    try:
        yield
    finally:
        _active_profile.reset(token)


def current_vault_path(default: str) -> str:
    profile = _active_profile.get()
    return profile.vault_path if profile is not None else default


def current_embeddings_path(default: str) -> str:
    profile = _active_profile.get()
    return profile.embeddings_path if profile is not None else default
