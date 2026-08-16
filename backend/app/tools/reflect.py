"""Tool de reflexión/memoria abstracta del agente (`jarvis_reflect`).

Guarda ideas o decisiones abstraídas de tareas resueltas en un JSONL
append-only (`settings.reflections_path`) y permite consultarlas por tema más
adelante, para que el modelo tenga continuidad de criterio entre
conversaciones distintas (que no comparten historial) sin depender de que el
usuario repita contexto. Búsqueda simple por superposición de palabras --no
hay embeddings ni LLM de por medio-- alcanza para un log personal de un solo
usuario.

Esquema por entrada (rediseño 2026-08-13, confirmado por Damian): además de
`timestamp`/`insight` originales, cada entrada lleva:
- `tipo`: "decision_arquitectura" | "preferencia_usuario" | "leccion_aprendida"
  | "ruido" -- permite filtrar por CLASE de reflexión, no solo por palabra
  clave. Default "leccion_aprendida" (el cajón neutral de "algo aprendido"
  cuando no se especifica algo más puntual) -- nunca "ruido" por default,
  eso devaluaría toda entrada nueva de arranque, contrario al propósito de
  la tool.
- `contexto`: a qué parte de Jarvis aplica (ej. "modulo_investigacion",
  "desktop_control", "general") -- evita que todo quede en una sola bolsa
  sin distinción de subsistema. Default "general".
- `vigente`: bool, default True -- mismo principio de trazabilidad que ya
  usa app/investigation/ (nunca borrar, solo marcar como retractado):
  algo que dejó de aplicar se marca `vigente=false`, nunca se elimina la
  entrada. `_query` EXCLUYE `vigente=false` por default (mismo criterio
  que `case_store._load_active_case` excluye nodos retractados de la
  vista activa) -- para revisar lo descartado hay que pedirlo explícito
  con `vigente=false`.

Retrocompatibilidad de lectura: entradas viejas (pre-rediseño) sin estos
campos siguen siendo legibles -- `_query` usa `.get()` con defaults, nunca
asume que el campo está."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from . import register_tool

TIPOS_VALIDOS = frozenset({"decision_arquitectura", "preferencia_usuario", "leccion_aprendida", "ruido"})
_TIPO_DEFAULT = "leccion_aprendida"
_CONTEXTO_DEFAULT = "general"

# Bug real, grave, encontrado en testing adversarial (2026-08-13, "múltiples
# conversaciones consultando jarvis_reflect a la vez"): sin ningún lock, cada
# `_save` abre su PROPIO file handle en modo 'a' -- confirmado en vivo que
# guardados concurrentes (50 threads) podían perder una entrada en silencio
# (49 líneas en el archivo en vez de 50, SIN ningún error, el caller recibía
# {"saved": True} igual) -- Windows no garantiza que un `write()` desde
# handles de append independientes sea atómico entre sí, a diferencia de
# POSIX con O_APPEND. Un solo archivo global (no hay concepto de "caso" acá
# como en app/investigation/), así que un lock simple a nivel de módulo
# alcanza -- mismo criterio que `_lock_for` de case_store.py, escala más chica.
_write_lock = threading.Lock()


def _reflections_path() -> Path:
    return Path(settings.reflections_path)


def _save(
    insight: str, tipo: str = _TIPO_DEFAULT, contexto: str = _CONTEXTO_DEFAULT, vigente: bool = True
) -> dict:
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"tipo inválido: '{tipo}' (debe ser uno de {sorted(TIPOS_VALIDOS)})")
    path = _reflections_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(), "insight": insight,
        "tipo": tipo, "contexto": contexto, "vigente": vigente,
    }
    with _write_lock:
        with path.open("a", encoding="utf-8") as f:
            # Bug real encontrado en testing adversarial (2026-08-13, "kill
            # duro a mitad de un write"): un kill que interrumpe un write()
            # deja la última línea SIN el '\n' final -- si la próxima
            # entrada se agrega directo con `open('a')`, queda pegada al
            # final de esa línea rota (sin separador), formando UNA sola
            # línea inválida que ni siquiera el manejo tolerante de
            # `_load_entries` puede salvar -- la entrada NUEVA, perfectamente
            # válida en sí misma, se pierde en silencio junto con la vieja.
            # Confirmado en vivo truncando una línea a mano y guardando la
            # siguiente. Se asegura acá que el archivo SIEMPRE termine en
            # '\n' antes de escribir la entrada nueva -- así una línea rota
            # queda aislada en su propia línea (se sigue perdiendo ESA, pero
            # nunca contamina a la siguiente).
            if path.stat().st_size > 0:
                with path.open("rb") as check:
                    check.seek(-1, 2)
                    if check.read(1) != b"\n":
                        f.write("\n")
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"saved": True, "timestamp": entry["timestamp"], "tipo": tipo, "contexto": contexto, "vigente": vigente}


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


def _query(
    topic: str, limit: int, tipo: str | None = None, contexto: str | None = None, vigente: bool | None = True
) -> dict:
    """`vigente=True` (default) excluye lo marcado como descartado --mismo
    criterio que la vista activa del módulo de investigación-- pasar
    `vigente=False` explícito para revisar justamente lo descartado, o
    `vigente=None` para ignorar ese filtro y ver todo."""
    topic_words = set(topic.lower().split())
    scored = []
    for entry in _load_entries():
        if tipo is not None and entry.get("tipo", _TIPO_DEFAULT) != tipo:
            continue
        if contexto is not None and entry.get("contexto", _CONTEXTO_DEFAULT) != contexto:
            continue
        if vigente is not None and entry.get("vigente", True) != vigente:
            continue
        insight_words = set(entry.get("insight", "").lower().split())
        score = len(topic_words & insight_words)
        if score > 0:
            scored.append((score, entry["timestamp"], entry))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    results = [
        {
            "timestamp": entry["timestamp"], "insight": entry["insight"],
            "tipo": entry.get("tipo", _TIPO_DEFAULT), "contexto": entry.get("contexto", _CONTEXTO_DEFAULT),
            "vigente": entry.get("vigente", True),
        }
        for _, _, entry in scored[:limit]
    ]
    return {"topic": topic, "results": results}


@register_tool(
    name="jarvis_reflect",
    description=(
        "Memoria de reflexión del propio agente: guarda ideas, decisiones o conclusiones abstraídas "
        "de una tarea ya resuelta (action='save', con 'insight') para recordarlas en conversaciones "
        "futuras, o busca reflexiones guardadas relevantes a un tema (action='query', con 'topic') "
        "antes de actuar en una tarea ambigua o compleja. Usala para dejar registro de por qué se "
        "tomó una decisión no trivial (ej. 'el usuario prefiere X en vez de Y porque...'), no para "
        "guardar datos triviales o el estado de una tarea puntual. Cada entrada lleva 'tipo' y "
        "'contexto' para poder filtrar además de buscar por palabra clave -- usalos con criterio real "
        "al guardar, no dejes todo en los defaults por comodidad."
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
            "tipo": {
                "type": "string",
                "enum": sorted(TIPOS_VALIDOS),
                "description": (
                    "Clase de la reflexión (opcional en 'save', default 'leccion_aprendida'; opcional en "
                    "'query' para filtrar por clase). 'decision_arquitectura' = una decisión técnica tomada "
                    "y por qué; 'preferencia_usuario' = algo que Damian prefiere/pidió explícitamente; "
                    "'leccion_aprendida' = algo aprendido de un error o resultado; 'ruido' = quedó guardado "
                    "pero no es una reflexión real aprovechable (nunca uses esto para guardar algo nuevo a "
                    "propósito, es para marcar lo descartado, no para clasificar en el momento)."
                ),
            },
            "contexto": {
                "type": "string",
                "description": (
                    "A qué parte de Jarvis aplica esta reflexión (ej. 'modulo_investigacion', "
                    "'desktop_control', 'general'). Opcional en 'save' (default 'general'); opcional en "
                    "'query' para filtrar por subsistema."
                ),
            },
            "vigente": {
                "type": "boolean",
                "description": (
                    "Solo para 'query': default true (excluye lo marcado como descartado/obsoleto). Pasá "
                    "false para revisar justamente lo descartado."
                ),
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
    action: str,
    insight: str | None = None,
    topic: str | None = None,
    limit: int = 5,
    tipo: str | None = None,
    contexto: str | None = None,
    vigente: bool | None = True,
) -> dict:
    if action == "save":
        if not insight:
            raise ValueError("action='save' requiere 'insight'")
        save_kwargs = {}
        if tipo is not None:
            save_kwargs["tipo"] = tipo
        if contexto is not None:
            save_kwargs["contexto"] = contexto
        if vigente is not None:
            save_kwargs["vigente"] = vigente
        return _save(insight, **save_kwargs)
    if action == "query":
        if not topic:
            raise ValueError("action='query' requiere 'topic'")
        return _query(topic, limit, tipo=tipo, contexto=contexto, vigente=vigente)
    raise ValueError(f"action inválida: '{action}' (debe ser 'save' o 'query')")
