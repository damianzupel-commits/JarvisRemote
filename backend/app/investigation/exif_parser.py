"""Metadatos EXIF de imágenes + descripción visual asistida por modelo
(spec sección 2, paso 6: "Metadatos EXIF de imágenes -- aprovechá el
modelo de visión para lo que EXIF no da").

Dos partes bien separadas, mismo principio de todo el módulo (nunca
mezclar dato verificado con salida de modelo sin etiquetar):

1. `extract_exif_metadata` -- determinístico, sin modelo. Lee tags EXIF
   reales (fecha de captura, GPS, cámara) directamente de los bytes de la
   imagen con Pillow. Esto es lo único que puede terminar en el campo
   `descripcion`/`timestamp_utc` de un nodo `Evento` real.
2. `describe_image_content` -- el modelo de visión (mismo modelo único del
   proyecto, `settings.lmstudio_model` -- no todo modelo cargado es VL,
   ver `app/agent.py::awaiting_vision_response` para el mismo criterio de
   fallback si no lo es) describe lo que se VE en la imagen (personas,
   objetos, texto visible, escena) -- algo que EXIF nunca da. Esta
   descripción NUNCA entra directo al grafo: se reusa el pipeline de NER ya
   existente (`ner.propose_entities`) pasándole el texto de la descripción
   como si fuera cualquier otro texto no estructurado -- mismo estado
   "pendiente de confirmación", misma trazabilidad hacia el Archivo de
   origen, sin duplicar la lógica de confirmar/rechazar que ya existe.

GPS EXIF no tiene un tipo de nodo dedicado en el schema (spec sección 1 no
define "Ubicación") -- se guarda como parte de la `descripcion` de un nodo
`Evento` ("foto tomada en lat,lon"), no se inventa un tipo de nodo nuevo
para esto."""

from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import GPSTAGS, IFD

from ..config import settings
from ..llm_client import client
from . import artifact_store, case_store, timeline
from .models import DerivadaPor, EdgeType, Node, make_archivo, make_edge, make_evento

_VISION_SYSTEM_PROMPT = (
    "Sos un asistente de análisis visual para un caso de investigación. Te dan una imagen y tenés que "
    "describir OBJETIVAMENTE lo que se ve -- personas presentes (sin identificarlas, solo describir lo "
    "visible: cantidad, vestimenta, acción), objetos, texto legible (carteles, matrículas, pantallas), y el "
    "entorno/escena. NUNCA concluyas quién es alguien, NUNCA inventes contexto que no se ve directamente en "
    "la imagen, NUNCA especules sobre intención o culpabilidad. Respondé en un párrafo breve, en español, "
    "solo con lo que es visualmente verificable."
)


def _dms_to_decimal(dms: tuple[float, float, float], ref: str) -> float:
    degrees, minutes, seconds = dms
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    return -decimal if ref in ("S", "W") else decimal


def _extract_gps(exif) -> tuple[float, float] | None:
    gps_ifd = exif.get_ifd(IFD.GPSInfo)
    if not gps_ifd:
        return None
    gps_tags = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
    lat, lat_ref = gps_tags.get("GPSLatitude"), gps_tags.get("GPSLatitudeRef")
    lon, lon_ref = gps_tags.get("GPSLongitude"), gps_tags.get("GPSLongitudeRef")
    if not (lat and lat_ref and lon and lon_ref):
        return None
    return _dms_to_decimal(lat, lat_ref), _dms_to_decimal(lon, lon_ref)


def _exif_datetime_to_iso(raw: str) -> str:
    """El formato nativo de EXIF es "AAAA:MM:DD HH:MM:SS" (dos puntos en la
    fecha, no guiones) -- bug real encontrado probando esto: pasarlo tal
    cual a `dateutil.parser.parse` lo interpreta MAL (confirmado con
    "2026:08:12 14:30:00" -> devolvía el día 13, no el 12). El formato EXIF
    nunca es ambiguo (siempre AAAA:MM:DD, orden fijo por el propio
    estándar), así que se convierte directo a ISO 8601 real ANTES de
    pasarlo a `timeline.normalize_timestamp` -- así entra por el camino
    estricto (`datetime.fromisoformat`), sin ninguna heurística de por
    medio."""
    date_part, _, time_part = raw.partition(" ")
    return f"{date_part.replace(':', '-')} {time_part}"


def extract_exif_metadata(image_bytes: bytes) -> dict[str, Any]:
    img = Image.open(io.BytesIO(image_bytes))
    exif = img.getexif()
    if not exif:
        return {}

    result: dict[str, Any] = {
        "make": exif.get(0x010F),  # Make
        "model": exif.get(0x0110),  # Model
        "software": exif.get(0x0131),  # Software
    }

    exif_sub = exif.get_ifd(IFD.Exif)
    raw_datetime = exif_sub.get(0x9003) or exif.get(0x0132)  # DateTimeOriginal, o DateTime si no hay
    if raw_datetime:
        result["datetime_original_raw"] = raw_datetime

    gps = _extract_gps(exif)
    if gps:
        result["gps_lat"], result["gps_lon"] = gps

    return {k: v for k, v in result.items() if v is not None}


def ingest_image(
    *, cases_dir: str | Path, keys_dir: str | Path, artifact_store_dir: str | Path, case_id: str,
    image_bytes: bytes, original_filename: str, ingested_by: str,
) -> dict:
    """Determinístico -- sin modelo. Crea el nodo Archivo (siempre) y, SOLO
    si el EXIF trae una fecha de captura real, un nodo Evento (Evento
    exige `timestamp_utc` como campo obligatorio -- no se inventa uno si
    el EXIF no lo trae). La descripción visual del modelo es un paso
    APARTE (ver `describe_image_content` + `ner.propose_entities`), no
    ocurre acá."""
    record = artifact_store.store_artifact(artifact_store_dir, image_bytes, original_filename, ingested_by)
    archivo_node = make_archivo(
        nombre=original_filename, sha256=record.sha256, tamano=record.size, mime=record.mime or "image/jpeg",
    )
    archivo_node = case_store.add_node(cases_dir, keys_dir, case_id, archivo_node)

    try:
        exif = extract_exif_metadata(image_bytes)
    except UnidentifiedImageError as exc:
        raise ValueError(f"'{original_filename}' no es una imagen reconocible (¿archivo vacío o corrupto?)") from exc

    evento_node: Node | None = None
    raw_datetime = exif.get("datetime_original_raw")
    if raw_datetime:
        try:
            normalized = timeline.normalize_timestamp(_exif_datetime_to_iso(raw_datetime))
        except (ValueError, TypeError, OverflowError):
            normalized = None
        if normalized is not None:
            descripcion_partes = [f"Foto capturada ({original_filename})"]
            if exif.get("make") or exif.get("model"):
                descripcion_partes.append(f"cámara: {exif.get('make', '')} {exif.get('model', '')}".strip())
            if "gps_lat" in exif and "gps_lon" in exif:
                descripcion_partes.append(f"GPS: {exif['gps_lat']:.6f}, {exif['gps_lon']:.6f}")
            evento_node = case_store.add_node(cases_dir, keys_dir, case_id, make_evento(
                timestamp_utc=normalized.utc, descripcion=" -- ".join(descripcion_partes), fuente="exif",
            ))
            # Bug real encontrado con la validación end-to-end del módulo:
            # a diferencia de csv_parser/chat_parser/server_log_parser, acá
            # faltaba la arista aparece_en Evento -> Archivo -- el nodo
            # Evento quedaba huérfano de trazabilidad, violando el criterio
            # de aceptación de la spec ("todo nodo se puede rastrear hasta
            # un artefacto con hash verificable, en un clic"). Mismo patrón
            # que el resto de los parsers, corregido acá.
            case_store.add_edge(cases_dir, keys_dir, case_id, make_edge(
                tipo=EdgeType.APARECE_EN, origen=evento_node.id, destino=archivo_node.id,
                artefacto_origen=archivo_node.id, confianza=1.0, derivada_por=DerivadaPor.PARSER,
                timestamp=normalized.utc,
            ))

    return {"archivo": archivo_node, "evento": evento_node, "exif": exif}


async def describe_image_content(image_bytes: bytes, mime_type: str = "image/jpeg") -> str | None:
    """Devuelve una descripción en texto plano de lo que se VE en la
    imagen, o None si el modelo actualmente cargado no soporta visión
    (mismo criterio de fallback que `app/agent.py::awaiting_vision_response`
    -- no todo modelo cargado en esta instalación es VL). Nunca escribe
    nada por sí sola -- quien llama decide si pasa el resultado a
    `ner.propose_entities` para convertirlo en propuestas de entidad
    pendientes de confirmación."""
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        response = await client.chat.completions.create(
            model=settings.lmstudio_model,
            messages=[
                {"role": "system", "content": _VISION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                        {"type": "text", "text": "Describí objetivamente lo que se ve en esta imagen."},
                    ],
                },
            ],
            temperature=0,
            max_tokens=512,
        )
    except Exception:
        return None
    return response.choices[0].message.content or None
