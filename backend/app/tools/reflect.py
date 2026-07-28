"""Tool de reflexión/memoria abstracta del agente (`jarvis_reflect`).

Guarda ideas o decisiones abstraídas de tareas resueltas en un JSONL
append-only (`settings.reflections_path`) y permite consultarlas por tema más
adelante, para que el modelo tenga continuidad de criterio entre
conversaciones distintas (que no comparten historial) sin depender de que el
usuario repita contexto. Búsqueda simple por superposición de palabras --no
hay embeddings ni LLM de por medio-- alcanza para un log personal de un solo
usuario.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from . import register_tool


def _reflections_path() -> Path:
    return Path(settings.reflections_path)


def _save(insight: str) -> dict:
    path = _reflections_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "insight": insight}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"saved": True, "timestamp": entry["timestamp"]}


def _load_entries() -> list[dict]:
    path = _reflections_path()
    if not path.exists():
        return []
    entries = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _query(topic: str, limit: int) -> dict:
    topic_words = set(topic.lower().split())
    scored = []
    for entry in _load_entries():
        insight_words = set(entry.get("insight", "").lower().split())
        score = len(topic_words & insight_words)
        if score > 0:
            scored.append((score, entry["timestamp"], entry["insight"]))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    results = [{"timestamp": ts, "insight": insight} for _, ts, insight in scored[:limit]]
    return {"topic": topic, "results": results}


@register_tool(
    name="jarvis_reflect",
    description=(
        "Memoria de reflexión del propio agente: guarda ideas, decisiones o conclusiones abstraídas "
        "de una tarea ya resuelta (action='save', con 'insight') para recordarlas en conversaciones "
        "futuras, o busca reflexiones guardadas relevantes a un tema (action='query', con 'topic') "
        "antes de actuar en una tarea ambigua o compleja. Usala para dejar registro de por qué se "
        "tomó una decisión no trivial (ej. 'el usuario prefiere X en vez de Y porque...'), no para "
        "guardar datos triviales o el estado de una tarea puntual."
    ),
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save", "query"],
                "description": "'save' para guardar una reflexión nueva, 'query' para buscar reflexiones existentes.",
            },
            "insight": {
                "type": "string",
                "description": "Requerido si action='save': la idea/decisión a recordar, en una o dos frases.",
            },
            "topic": {
                "type": "string",
                "description": "Requerido si action='query': tema o palabras clave a buscar entre las reflexiones guardadas.",
            },
            "limit": {
                "type": "integer",
                "description": "Máximo de resultados para action='query' (default 5).",
            },
        },
        "required": ["action"],
    },
)
def jarvis_reflect(
    action: str, insight: str | None = None, topic: str | None = None, limit: int = 5
) -> dict:
    if action == "save":
        if not insight:
            raise ValueError("action='save' requiere 'insight'")
        return _save(insight)
    if action == "query":
        if not topic:
            raise ValueError("action='query' requiere 'topic'")
        return _query(topic, limit)
    raise ValueError(f"action inválida: '{action}' (debe ser 'save' o 'query')")
