"""Pipeline automático de ingesta de videos de YouTube al vault de Obsidian
(ver `app/obsidian/vault.py`), pensado para reemplazar el flujo MANUAL con el
que Damian venía procesando su playlist "Info para Jarvis": pasar cada video
por NotebookLM a mano y copiar el resumen a una nota.

Flujo (todo con piezas reales del repo, nada simulado en producción):

  1. Enumera los videos de una playlist con `yt-dlp --flat-playlist` (solo
     id + título + canal, sin bajar los videos).
  2. Detecta los NUEVOS: los que están en la playlist pero todavía no tienen
     una nota en el vault. La detección es por VIDEO ID (los 11 chars de
     `watch?v=<ID>`), parseado del cuerpo de las notas ya existentes -- NO por
     título (los títulos de las notas están curados y no coinciden con el del
     video), así el pipeline es idempotente: correrlo dos veces no duplica.
  3. Para cada nuevo, obtiene la transcripción (prefiere español, cae a
     inglés) y con ella genera el resumen llamando al MISMO LLM de chat que ya
     usa Jarvis (`app/llm_client.py` + `settings.lmstudio_model`), sin
     duplicar cliente.
  4. Escribe la nota replicando EXACTO el formato de las notas existentes
     (frontmatter author=jarvis, tags [info-para-jarvis, video, <categoría>],
     secciones ## Fuente / ## Resumen / ## Temas clave / ## Notas relacionadas
     con wikilinks), con "Generado con: resumen automático" en ## Fuente en
     lugar del NotebookLM de las notas viejas. Actualiza el índice
     `Playlist: Información para Jarvis (YouTube)` agregando el wikilink y
     recalculando el conteo de videos.

Un video sin transcripción disponible se salta con gracia (se reporta, no se
crea una nota vacía ni se rompe la corrida entera).

┌─────────────────────────────────────────────────────────────────────────┐
│ ⚠️  NO PROBADO CONTRA YOUTUBE REAL. El entorno donde se escribió este     │
│ módulo tiene YouTube bloqueado por red, así que el pipeline NUNCA corrió  │
│ end-to-end contra la API/subtítulos reales de YouTube -- solo contra      │
│ mocks (ver backend/tests/test_youtube_ingestion.py). La lógica de vault,  │
│ detección de nuevos, formato de nota, idempotencia e índice sí está       │
│ testeada. Damian tiene que correrlo UNA vez en su PC (con red a YouTube y │
│ el LLM levantado) para validar que `yt-dlp` y `youtube-transcript-api`    │
│ devuelven lo que este código espera antes de confiar en él.               │
└─────────────────────────────────────────────────────────────────────────┘

Uso:

  CLI:   python -m app.ingestion.youtube_playlist <URL_de_la_playlist>
  Tool:  registrada como `youtube_ingest_playlist` (ver app/tools/ingestion.py),
         así Jarvis la puede disparar por voz/chat.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from ..config import settings
from ..llm_client import client
from ..obsidian import vault

# Título e id de la nota índice de la playlist (ya existe en el vault, creada
# a mano cuando el flujo era manual). Se actualiza in-place con note_id para
# no romper su slug/frontmatter.
INDEX_NOTE_ID = "jarvis/playlist-informacion-para-jarvis-youtube"
INDEX_NOTE_TITLE = "Playlist: Información para Jarvis (YouTube)"

# URL default de la playlist personal de Damian ("Info para Jarvis"), la que
# alimentaba el flujo manual -- así la CLI/tool se pueden llamar sin argumento.
DEFAULT_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLVjx_ae3DGSo"

# Un video ID de YouTube son exactamente 11 chars del alfabeto base64-url.
_VIDEO_ID_RE = re.compile(r"(?:v=|/watch\?v=|youtu\.be/)([0-9A-Za-z_-]{11})")

# Idiomas de subtítulos a pedir, en orden de preferencia (español primero,
# inglés como fallback -- pedido explícito).
_TRANSCRIPT_LANGS = ["es", "es-419", "es-ES", "en", "en-US"]

# Tope de caracteres de transcripción que se le manda al LLM. Una
# transcripción larga (video de 30 min) puede superar el presupuesto de
# contexto del modelo (ver settings.model_context_tokens) -- se recorta para
# no disparar el context-shift de Ollama (mismo problema documentado en
# app/agent.py). El resumen igual capta la idea con el arranque del video.
_MAX_TRANSCRIPT_CHARS = 12000

# Temas de interés del proyecto Jarvis contra los que se juzga la UTILIDAD de
# cada video (agregado 2026-08-18, decisión de Damian). Configurable: se puede
# pasar otra lista a `ingest_playlist(..., relevance_topics=[...])`. Estos son
# los defaults.
#
# ⚠️ FILOSOFÍA (no debilitar sin pedírselo a Damian): la relevancia es una
# SEÑAL/ETIQUETA, NUNCA un filtro que descarta. Aunque un video puntúe bajo hoy,
# es info que Damian curó a mano y que "tal vez un día le sirva" -- así que TODO
# se guarda. La única forma de que la relevancia saltee un video es que Damian
# lo pida explícito con --min-relevance N (default: no filtra nada).
DEFAULT_RELEVANCE_TOPICS = [
    "ciberseguridad ofensiva y defensiva",
    "hacking",
    "IA y agentes",
    "métodos de aprendizaje",
    "robótica y exoesqueletos",
    "desarrollo del propio asistente Jarvis",
]

# Veredictos canónicos que puede devolver el discernimiento de relevancia, en
# orden de mayor a menor utilidad. El LLM puede escribir variantes (con/sin
# tilde, "util", etc.); `_parse_relevance` las normaliza a uno de estos.
_RELEVANCE_VERDICTS = ["útil", "dudoso", "no útil"]

# Umbral por debajo del cual (o con veredicto "no útil") una nota se marca como
# baja relevancia: tag `baja-relevancia` + advertencia visible en la nota. NO
# borra ni saltea -- solo etiqueta.
_LOW_RELEVANCE_SCORE = 2


@dataclass
class VideoEntry:
    """Un video tal como lo devuelve `yt-dlp --flat-playlist`."""

    video_id: str
    title: str
    channel: str = ""
    duration: str = ""


@dataclass
class IngestResult:
    """Resultado de una corrida del pipeline (serializable a dict para la
    tool del agente)."""

    playlist_url: str
    total_in_playlist: int = 0
    already_present: list[str] = field(default_factory=list)  # video_ids ya en el vault
    created: list[dict] = field(default_factory=list)  # {video_id, note_id, title, relevancia, relevancia_score}
    skipped_no_transcript: list[dict] = field(default_factory=list)  # {video_id, title}
    # ERRORES TÉCNICOS al obtener la transcripción (IpBlocked, VideoUnavailable,
    # cambio de API, timeout, etc.). NO es lo mismo que "sin subtítulos": acá va
    # lo que falló por un problema técnico, con su motivo real, para que NO se
    # oculte como si el video no tuviera transcripción. {video_id, title, error}
    transcript_errors: list[dict] = field(default_factory=list)
    # Saltados SOLO por --min-relevance explícito de Damian (no por juicio de
    # relevancia por default -- por default nada se saltea). {video_id, title,
    # relevancia, relevancia_score}
    skipped_low_relevance: list[dict] = field(default_factory=list)

    def relevance_breakdown(self) -> dict:
        """Conteo de notas creadas por veredicto de relevancia, para el resumen
        final (ej. útil: 6, dudoso: 2, no útil: 1)."""
        counts = {v: 0 for v in _RELEVANCE_VERDICTS}
        for c in self.created:
            verdict = c.get("relevancia")
            if verdict in counts:
                counts[verdict] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "playlist_url": self.playlist_url,
            "total_in_playlist": self.total_in_playlist,
            "created_count": len(self.created),
            "already_present_count": len(self.already_present),
            "skipped_no_transcript_count": len(self.skipped_no_transcript),
            "transcript_errors_count": len(self.transcript_errors),
            "skipped_low_relevance_count": len(self.skipped_low_relevance),
            "relevance_breakdown": self.relevance_breakdown(),
            "created": self.created,
            "already_present": self.already_present,
            "skipped_no_transcript": self.skipped_no_transcript,
            "transcript_errors": self.transcript_errors,
            "skipped_low_relevance": self.skipped_low_relevance,
        }


# ---------------------------------------------------------------------------
# Adaptadores hacia librerías externas (yt-dlp / youtube-transcript-api / LLM).
# Se aíslan en funciones finas a propósito: son los ÚNICOS puntos que tocan la
# red real de YouTube o el LLM, así los tests los mockean sin tener que
# simular toda la mecánica interna del pipeline.
# ---------------------------------------------------------------------------


def fetch_playlist_entries(playlist_url: str) -> list[VideoEntry]:
    """Enumera los videos de la playlist con `yt-dlp` en modo flat (sin bajar
    los videos, solo metadata). Import perezoso de yt_dlp para que el módulo
    se pueda importar (y testear) sin la dependencia instalada."""
    import yt_dlp  # import perezoso -- ver docstring

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,  # equivalente a --flat-playlist: no resuelve cada video
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    entries = info.get("entries") or []
    result: list[VideoEntry] = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id") or ""
        if not video_id:
            continue
        result.append(
            VideoEntry(
                video_id=video_id,
                title=(entry.get("title") or "").strip() or video_id,
                channel=(entry.get("channel") or entry.get("uploader") or "").strip(),
                duration=_format_duration(entry.get("duration")),
            )
        )
    return result


def fetch_transcript(video_id: str) -> str | None:
    """Baja la transcripción del video (prefiere español, cae a inglés).
    Devuelve el texto plano concatenado, o None si el video REALMENTE no tiene
    subtítulos disponibles en los idiomas pedidos. Import perezoso, mismo motivo
    que `fetch_playlist_entries`.

    ⚠️ API youtube-transcript-api 1.2.x (2026-08-18): la versión instalada en la
    PC de Damian es 1.2.4, donde el classmethod viejo `YouTubeTranscriptApi
    .get_transcript(video_id, languages=...)` -> lista de dicts YA NO EXISTE. La
    API correcta es de INSTANCIA: `YouTubeTranscriptApi().fetch(video_id,
    languages=[...])` -> un `FetchedTranscript` cuyos `.snippets` son
    `FetchedTranscriptSnippet` con atributos `.text`/`.start`/`.duration` (NO
    dicts). El bug anterior tiraba AttributeError contra la 1.2.4 en TODOS los
    videos y el `except Exception` lo disfrazaba de "sin transcripción", así que
    la playlist entera se salteaba aunque los videos sí tuvieran subtítulos.

    Manejo de errores (pedido explícito de Damian): SOLO `TranscriptsDisabled` y
    `NoTranscriptFound` significan "este video no tiene subtítulos utilizables"
    -> se devuelve None (se saltea con gracia) dejando registrado el motivo real.
    Cualquier OTRA excepción (IpBlocked, RequestBlocked, VideoUnavailable, cambio
    de API, timeout, etc.) es un ERROR TÉCNICO y se deja PROPAGAR para que
    `ingest_playlist` lo reporte con su tipo y mensaje, en vez de ocultarlo como
    si fuera falta de subtítulos."""
    from youtube_transcript_api import (  # import perezoso
        YouTubeTranscriptApi,
        TranscriptsDisabled,
        NoTranscriptFound,
    )

    api = YouTubeTranscriptApi()
    try:
        fetched = api.fetch(video_id, languages=_TRANSCRIPT_LANGS)
    except TranscriptsDisabled as exc:
        # Subtítulos DESHABILITADOS por el autor: no hay nada que traducir. Se
        # saltea con gracia dejando el motivo real en el log.
        print(f"[youtube_ingest] {video_id}: sin transcripción ({type(exc).__name__}: {exc})")
        return None
    except NoTranscriptFound as exc:
        # No hay subtítulos DIRECTOS en es/en, pero puede haber una transcripción
        # en otro idioma (p.ej. auto-generada en portugués) que YouTube marca como
        # traducible. Antes de rendirnos, intentamos traducirla a es/en. Mejor
        # esfuerzo: si la traducción falla por cualquier motivo, se saltea igual.
        translated = _fetch_translated_transcript(api, video_id)
        if translated is not None:
            return translated
        print(f"[youtube_ingest] {video_id}: sin transcripción ({type(exc).__name__}: {exc})")
        return None
    # Nota: cualquier otra excepción se propaga a propósito (ver docstring).

    text = " ".join((snippet.text or "").strip() for snippet in fetched.snippets if snippet.text)
    text = text.strip()
    return text or None


# Idiomas destino de traducción, en orden de preferencia. A diferencia de
# _TRANSCRIPT_LANGS (que incluye variantes regionales para el match DIRECTO), acá
# usamos los códigos base que YouTube expone como destinos de traducción.
_TRANSLATE_TARGET_LANGS = ("es", "en")


def _fetch_translated_transcript(api, video_id: str) -> str | None:
    """Fallback de traducción (agregado 2026-08-26, pedido de Damian): cuando no
    hay transcripción directa en los idiomas pedidos, busca cualquier
    transcripción traducible del video y la traduce al primer idioma preferido
    disponible (es -> en). Devuelve el texto plano o None si nada es traducible.

    Coherente con el principio del módulo (ver docstring de `fetch_transcript`):
    NO oculta errores técnicos. Solo `NoTranscriptFound`/`TranscriptsDisabled` al
    LISTAR significan "no hay nada que traducir" -> devuelve None (se saltea con
    gracia). Cualquier OTRA excepción (SSL, timeout, red, cambio de API) se
    PROPAGA para que `ingest_playlist` la reporte como error técnico real, en vez
    de disfrazarla de "sin transcripción". Devuelve el texto traducido o None si
    ninguna transcripción es traducible a es/en."""
    from youtube_transcript_api import (  # import perezoso
        NoTranscriptFound,
        TranscriptsDisabled,
    )

    try:
        transcript_list = api.list(video_id)
    except (NoTranscriptFound, TranscriptsDisabled):
        # Realmente no hay transcripciones que listar -> nada que traducir.
        return None
    # Cualquier otra excepción (red/API) se propaga a propósito.

    for target in _TRANSLATE_TARGET_LANGS:
        for transcript in transcript_list:
            if not getattr(transcript, "is_translatable", False):
                continue
            available = set()
            for tl in getattr(transcript, "translation_languages", None) or []:
                code = getattr(tl, "language_code", None)
                if code is None and isinstance(tl, dict):
                    code = tl.get("language_code")
                if code:
                    available.add(code)
            if target not in available:
                continue
            # translate().fetch() puede tirar errores técnicos (SSL/timeout): se
            # dejan PROPAGAR, no se ocultan.
            fetched = transcript.translate(target).fetch()
            text = " ".join(
                (s.text or "").strip() for s in fetched.snippets if s.text
            ).strip()
            if text:
                src = getattr(transcript, "language_code", "?")
                print(
                    f"[youtube_ingest] {video_id}: transcripción traducida a "
                    f"'{target}' desde '{src}'"
                )
                return text
    return None


async def _call_llm(messages: list[dict]) -> str:
    """Único punto que le pega al LLM de chat de Jarvis -- reusa el cliente
    async y el modelo ya configurados (`app/llm_client.py` +
    settings.lmstudio_model), no crea un cliente nuevo. Aislado en su propia
    función para que los tests lo mockeen sin simular la API de OpenAI."""
    response = await client.chat.completions.create(
        model=settings.lmstudio_model,
        messages=messages,
        temperature=0.3,
        max_tokens=settings.reserved_response_tokens,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Lógica del pipeline (100% testeable sin red).
# ---------------------------------------------------------------------------


def _format_duration(seconds) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    minutes, sec = divmod(total, 60)
    return f"{minutes}:{sec:02d}"


def existing_video_ids() -> set[str]:
    """IDs de video que YA tienen nota en el vault, parseados del cuerpo de
    las notas del autor 'jarvis' (la línea `- Video: https://...watch?v=<ID>`).
    Es lo que hace idempotente al pipeline: se detecta por ID, no por título."""
    ids: set[str] = set()
    for note in vault.list_notes(author="jarvis"):
        for match in _VIDEO_ID_RE.finditer(note.content):
            ids.add(match.group(1))
    return ids


def select_new_videos(entries: list[VideoEntry], already: set[str]) -> list[VideoEntry]:
    """Filtra los videos de la playlist que todavía no están en el vault.
    Deduplica por ID dentro de la propia playlist también (una playlist puede
    listar el mismo video dos veces)."""
    new: list[VideoEntry] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.video_id in already or entry.video_id in seen:
            continue
        seen.add(entry.video_id)
        new.append(entry)
    return new


def _summary_messages(entry: VideoEntry, transcript: str) -> list[dict]:
    """Prompt para el LLM: pedimos JSON estricto con título curado, categoría,
    resumen y temas clave -- el mismo esqueleto que tienen las notas
    existentes hechas con NotebookLM."""
    system = (
        "Sos el asistente Jarvis. Te paso la transcripción de un video de YouTube y tenés que "
        "resumirlo para el vault de conocimiento de Damian. Respondé SOLO con un objeto JSON válido "
        "(sin texto extra, sin markdown, sin ```), con estas claves exactas:\n"
        '  "title": un título curado y descriptivo en español para la nota (NO el título original '
        "del video, uno que describa el CONTENIDO real, como haría un editor).\n"
        '  "category": una sola palabra/frase corta en minúsculas para la categoría temática '
        "(ej. pentesting, programacion, osint, productividad, asistentes-ia, actualidad-ia).\n"
        '  "summary": un resumen denso de 4 a 6 oraciones, en español, en un solo párrafo.\n'
        '  "key_topics": una lista de 4 a 6 strings con los temas clave (frases cortas).'
    )
    user = (
        f'Título original del video: "{entry.title}"\n'
        f"Canal: {entry.channel or 'desconocido'}\n\n"
        f"Transcripción (puede estar recortada):\n{transcript[:_MAX_TRANSCRIPT_CHARS]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_summary(raw: str, entry: VideoEntry) -> dict:
    """Parsea el JSON que devolvió el LLM, tolerando que lo envuelva en un
    bloque ```json ... ``` o le agregue texto alrededor. Cae a defaults
    razonables si falta alguna clave, para nunca romper por un modelo que se
    salió del formato."""
    text = raw.strip()
    # Si vino envuelto en un fence markdown, quedarse con lo de adentro.
    fence = re.search(r"\{.*\}", text, re.DOTALL)
    if fence:
        text = fence.group(0)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = {}

    title = (data.get("title") or "").strip() or entry.title
    category = (data.get("category") or "").strip().lower() or "general"
    summary = (data.get("summary") or "").strip() or "(sin resumen generado)"
    topics = data.get("key_topics") or []
    if not isinstance(topics, list):
        topics = []
    topics = [str(t).strip() for t in topics if str(t).strip()]
    return {"title": title, "category": category, "summary": summary, "key_topics": topics}


def _relevance_messages(entry: VideoEntry, transcript: str, topics: list[str]) -> list[dict]:
    """Prompt para el discernimiento de UTILIDAD: le pedimos al MISMO LLM que
    juzgue si el video le sirve al proyecto Jarvis, dados sus temas de interés.
    Pide JSON estricto -- mismo patrón que `_summary_messages` -- con veredicto,
    puntaje 1-5 y una justificación de una línea."""
    temas = "\n".join(f"  - {t}" for t in topics)
    system = (
        "Sos el asistente Jarvis evaluando si un video le sirve como información al PROYECTO Jarvis. "
        "Los temas de interés del proyecto son:\n"
        f"{temas}\n\n"
        "Te paso la transcripción de un video y tenés que juzgar qué tan útil/relevante es para esos temas. "
        "Respondé SOLO con un objeto JSON válido (sin texto extra, sin markdown, sin ```), con estas claves exactas:\n"
        '  "verdict": uno de exactamente estos tres valores: "útil", "dudoso", "no útil".\n'
        '  "score": un entero del 1 al 5 (1 = nada que ver con los temas, 5 = directamente sobre uno de ellos).\n'
        '  "reason": una sola oración corta en español justificando el veredicto.\n'
        "No filtres ni descartes nada: solo estás etiquetando. Un video poco relevante igual se guarda."
    )
    user = (
        f'Título original del video: "{entry.title}"\n'
        f"Canal: {entry.channel or 'desconocido'}\n\n"
        f"Transcripción (puede estar recortada):\n{transcript[:_MAX_TRANSCRIPT_CHARS]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _normalize_verdict(raw_verdict: str, score: int) -> str:
    """Normaliza el veredicto que escribió el LLM a uno de _RELEVANCE_VERDICTS,
    tolerando variantes (sin tilde, 'util', mayúsculas, 'no-util'). Si no se
    reconoce, cae al veredicto derivado del puntaje, así nunca queda vacío."""
    text = (raw_verdict or "").strip().lower()
    normalized = text.replace("-", " ")
    normalized = "".join(c for c in unicodedata.normalize("NFKD", normalized) if not unicodedata.combining(c))
    normalized = " ".join(normalized.split())
    if normalized in ("no util", "no utl", "inutil", "no relevante", "irrelevante"):
        return "no útil"
    if normalized in ("util", "utl", "relevante"):
        return "útil"
    if normalized in ("dudoso", "dudosa", "quizas", "tal vez", "medio"):
        return "dudoso"
    # No se reconoció el texto -> derivar del puntaje.
    if score <= _LOW_RELEVANCE_SCORE:
        return "no útil"
    if score >= 4:
        return "útil"
    return "dudoso"


def _parse_relevance(raw: str, entry: VideoEntry) -> dict:
    """Parsea el JSON del discernimiento de relevancia, con la misma tolerancia
    que `_parse_summary` (fence markdown / texto alrededor / claves faltantes).
    Devuelve siempre {verdict, score, reason} válidos -- nunca rompe la corrida
    por un modelo que se salió del formato; en el peor caso cae a 'dudoso'/3."""
    text = raw.strip()
    fence = re.search(r"\{.*\}", text, re.DOTALL)
    if fence:
        text = fence.group(0)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = {}

    # Puntaje: entero recortado a 1-5. Si no es parseable, default 3 (neutro).
    try:
        score = int(round(float(data.get("score"))))
    except (TypeError, ValueError):
        score = 3
    score = max(1, min(5, score))

    verdict = _normalize_verdict(str(data.get("verdict") or ""), score)

    reason = (data.get("reason") or "").strip()
    if not reason:
        reason = "(sin justificación generada)"
    # Una sola línea: colapsar saltos por si el modelo metió varias.
    reason = " ".join(reason.split())

    is_low = verdict == "no útil" or score <= _LOW_RELEVANCE_SCORE
    return {"verdict": verdict, "score": score, "reason": reason, "is_low": is_low}


def _build_note_content(entry: VideoEntry, summary: dict, relevance: dict) -> str:
    """Arma el Markdown de la nota replicando EXACTO el formato de las notas
    existentes (mismas secciones y wikilinks), cambiando solo la línea
    'Generado con:' a 'resumen automático'."""
    category = summary["category"]
    video_url = f"https://www.youtube.com/watch?v={entry.video_id}"
    duration = entry.duration or "desconocida"
    channel = entry.channel or "desconocido"

    parts = [
        f'Resumen automático generado a partir de la transcripción del video de YouTube '
        f'"{entry.title}", de la playlist personal de Damian "Info para Jarvis".',
        "",
        "## Fuente",
        f"- Video: {video_url}",
        f"- Canal: {channel}",
        f"- Duración: {duration}",
        "- Generado con: resumen automático",
        "",
        "## Resumen",
        summary["summary"],
        "",
        "## Temas clave",
    ]
    if summary["key_topics"]:
        parts.extend(f"- {topic}" for topic in summary["key_topics"])
    else:
        parts.append("- (no se extrajeron temas clave)")

    # ## Relevancia -- el discernimiento de utilidad para el proyecto. Es solo
    # una etiqueta: la nota se crea igual, incluso si es "no útil" (curaduría de
    # Damian). Para baja relevancia se antepone una advertencia visible.
    parts.extend(["", "## Relevancia"])
    if relevance["is_low"]:
        parts.append("⚠️ Marcada como baja relevancia — guardada igual por curaduría de Damian.")
    parts.extend(
        [
            f"- Veredicto: {relevance['verdict']}",
            f"- Puntaje: {relevance['score']}/5",
            f"- Razón: {relevance['reason']}",
        ]
    )

    parts.extend(
        [
            "",
            "## Notas relacionadas",
            f"- [[Índice: {category}]]",
            f"- [[{INDEX_NOTE_TITLE}]]",
        ]
    )
    return "\n".join(parts)


def _update_index(new_note_title: str, entry: VideoEntry, category: str) -> None:
    """Agrega el wikilink de la nota nueva al índice de la playlist y
    recalcula el conteo 'N videos.'. Idempotente: si el wikilink ya está, no
    hace nada."""
    try:
        index = vault.read_note(INDEX_NOTE_ID)
    except FileNotFoundError:
        # El índice debería existir siempre, pero si no está lo dejamos pasar
        # sin romper la ingesta (la nota igual quedó creada y linkeada al hub
        # de categoría).
        return

    wikilink = f"[[{new_note_title}]]"
    if wikilink in index.content:
        return  # ya listado -- idempotencia

    channel = entry.channel or "desconocido"
    bullet = f"- {wikilink} — {entry.title} ({channel}, categoría: {category})"

    content = index.content.rstrip("\n") + "\n" + bullet

    # Recalcular el conteo real de bullets de video y reescribir "N videos.".
    bullet_count = sum(1 for line in content.splitlines() if line.lstrip().startswith("- [["))
    content = re.sub(r"\b\d+\s+videos\.", f"{bullet_count} videos.", content)

    vault.save_note(
        title=index.title,
        content=content,
        author="jarvis",
        tags=index.tags,
        category=index.category,
        note_id=index.id,
    )


async def ingest_playlist(
    playlist_url: str = DEFAULT_PLAYLIST_URL,
    max_videos: int | None = None,
    relevance_topics: list[str] | None = None,
    min_relevance: int | None = None,
) -> IngestResult:
    """Corre el pipeline completo sobre una playlist. Async porque el resumen y
    el discernimiento de relevancia se generan con el LLM async de Jarvis.
    Idempotente: los videos ya presentes en el vault se saltan.

    `relevance_topics`: temas de interés contra los que se juzga la utilidad de
    cada video (default: DEFAULT_RELEVANCE_TOPICS).

    `min_relevance`: SOLO si Damian lo pide explícito -- saltea las notas con
    puntaje de relevancia menor a N (1-5). Default None = no filtra NADA: la
    relevancia es una etiqueta, no un filtro (ver filosofía en
    DEFAULT_RELEVANCE_TOPICS). Un video sin transcripción se salta aparte, eso
    NO es un juicio de relevancia."""
    playlist_url = (playlist_url or DEFAULT_PLAYLIST_URL).strip()
    topics = relevance_topics or DEFAULT_RELEVANCE_TOPICS
    entries = fetch_playlist_entries(playlist_url)
    already = existing_video_ids()

    result = IngestResult(playlist_url=playlist_url, total_in_playlist=len(entries))
    result.already_present = [e.video_id for e in entries if e.video_id in already]

    new_videos = select_new_videos(entries, already)
    if max_videos is not None:
        new_videos = new_videos[: max(0, int(max_videos))]

    for entry in new_videos:
        try:
            transcript = fetch_transcript(entry.video_id)
        except Exception as exc:
            # ERROR TÉCNICO al bajar la transcripción (no "falta de subtítulos":
            # eso lo maneja fetch_transcript devolviendo None). Se registra el
            # MOTIVO real (tipo + mensaje de la excepción) y se sigue con los
            # demás videos, en vez de tirar abajo la corrida o esconder el bug
            # como si el video no tuviera subtítulos.
            reason = f"{type(exc).__name__}: {exc}"
            print(
                f"[youtube_ingest] ERROR técnico de transcripción en {entry.video_id} "
                f"({entry.title}): {reason}"
            )
            result.transcript_errors.append(
                {"video_id": entry.video_id, "title": entry.title, "error": reason}
            )
            continue

        if not transcript:
            # Sin transcripción NO se puede procesar -- esto es independiente de
            # la relevancia (no es un juicio de utilidad, es que no hay material).
            result.skipped_no_transcript.append({"video_id": entry.video_id, "title": entry.title})
            continue

        # Discernimiento de relevancia + resumen, ambos con el MISMO LLM.
        raw_relevance = await _call_llm(_relevance_messages(entry, transcript, topics))
        relevance = _parse_relevance(raw_relevance, entry)

        # Filtro OPCIONAL por --min-relevance (solo a pedido explícito de Damian).
        # Por default (min_relevance is None) nunca entra acá: todo se guarda.
        if min_relevance is not None and relevance["score"] < min_relevance:
            result.skipped_low_relevance.append(
                {
                    "video_id": entry.video_id,
                    "title": entry.title,
                    "relevancia": relevance["verdict"],
                    "relevancia_score": relevance["score"],
                }
            )
            continue

        raw = await _call_llm(_summary_messages(entry, transcript))
        summary = _parse_summary(raw, entry)

        content = _build_note_content(entry, summary, relevance)
        # Baja relevancia -> tag extra `baja-relevancia` (además de los de
        # siempre). La nota se crea igual: es una señal, no un descarte.
        tags = ["info-para-jarvis", "video", summary["category"]]
        if relevance["is_low"]:
            tags.append("baja-relevancia")

        # Linkear la nota al hub de su categoría (mismo patrón que research.py)
        # antes de guardarla, así el índice de categoría existe y la nota nunca
        # queda huérfana del grafo.
        vault.link_note_to_category_index(summary["title"], category=summary["category"], author="jarvis")
        note = vault.save_note(
            title=summary["title"],
            content=content,
            author="jarvis",
            tags=tags,
            category=summary["category"],
            # relevancia como properties de frontmatter (ver save_note `extra`).
            extra={"relevancia": relevance["verdict"], "relevancia_score": relevance["score"]},
        )
        _update_index(note.title, entry, summary["category"])
        result.created.append(
            {
                "video_id": entry.video_id,
                "note_id": note.id,
                "title": note.title,
                "relevancia": relevance["verdict"],
                "relevancia_score": relevance["score"],
            }
        )

    return result


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Ingesta automática de una playlist de YouTube al vault de Obsidian de Jarvis."
    )
    parser.add_argument(
        "playlist_url",
        nargs="?",
        default=DEFAULT_PLAYLIST_URL,
        help=f"URL de la playlist (default: la de Damian, {DEFAULT_PLAYLIST_URL}).",
    )
    parser.add_argument("--max-videos", type=int, default=None, help="Tope de videos nuevos a procesar.")
    parser.add_argument(
        "--min-relevance",
        type=int,
        default=None,
        metavar="N",
        help=(
            "OPCIONAL. Saltea las notas con puntaje de relevancia menor a N (1-5). "
            "Por DEFAULT no filtra nada: la relevancia es solo una etiqueta, todo se guarda. "
            "Usalo solo si querés explícitamente descartar lo de baja relevancia en esta corrida."
        ),
    )
    args = parser.parse_args(argv)

    # Punto de entrada DESATENDIDO: esta CLI la corre un scheduler (ingesta
    # diaria de la playlist), sin un humano mirando. Declara modo AUTÓNOMO
    # explícitamente -- coincide con el default fail-safe del ContextVar, pero
    # dejarlo explícito documenta la intención y loguea el modo/roots efectivos
    # de la corrida. Ver app/operation_mode.py.
    from ..operation_mode import OperationMode, operating_as

    with operating_as(OperationMode.AUTONOMOUS, source="cli_youtube_ingestion"):
        result = asyncio.run(
            ingest_playlist(args.playlist_url, max_videos=args.max_videos, min_relevance=args.min_relevance)
        )

    breakdown = result.relevance_breakdown()
    breakdown_str = ", ".join(f"{v}: {breakdown[v]}" for v in _RELEVANCE_VERDICTS)

    print(f"Playlist: {result.playlist_url}")
    print(f"  Videos en la playlist: {result.total_in_playlist}")
    print(f"  Ya presentes en el vault: {len(result.already_present)}")
    print(f"  Notas nuevas creadas: {len(result.created)} ({breakdown_str})")
    for c in result.created:
        print(f"    + [{c['relevancia']} {c['relevancia_score']}/5] {c['title']}  ({c['video_id']})")
    print(f"  Saltados sin transcripción: {len(result.skipped_no_transcript)}")
    for s in result.skipped_no_transcript:
        print(f"    - {s['title']}  ({s['video_id']})")
    if result.transcript_errors:
        print(f"  Errores TÉCNICOS de transcripción: {len(result.transcript_errors)}")
        for e in result.transcript_errors:
            print(f"    ! {e['title']}  ({e['video_id']}): {e['error']}")
    if result.skipped_low_relevance:
        print(f"  Saltados por --min-relevance {args.min_relevance}: {len(result.skipped_low_relevance)}")
        for s in result.skipped_low_relevance:
            print(f"    - [{s['relevancia']} {s['relevancia_score']}/5] {s['title']}  ({s['video_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
