"""Tools del módulo de investigación (análisis de enlaces y evidencia
digital) -- expone `app/investigation/*` como capacidades reales de Jarvis,
en vez de dejarlo como plumbing interno sin forma de usarlo desde el chat.

Primer grupo, cada una mapea 1:1 a una etapa del flujo real (spec paso 2):
- `investigation_create_case`: arranca un caso nuevo (repo git propio).
- `investigation_propose_column_mapping`: el modelo PROPONE un mapeo de
  columnas -> campos del schema (rol acotado, spec sección 5 -- nunca
  decide el mapeo final, nunca escribe nada al grafo).
- `investigation_ingest_csv`: ingesta real end-to-end. Si no le pasan un
  `column_mapping` explícito, busca uno YA CONFIRMADO y guardado antes (por
  la firma de columnas, ver column_mapping.py) -- si tampoco hay uno
  guardado, no adivina: le dice al modelo que llame primero a
  investigation_propose_column_mapping y consiga la confirmación real de
  Damian antes de reintentar. Si SÍ le pasan `column_mapping` (porque Damian
  acaba de confirmar uno en su mensaje), lo usa Y lo guarda para la próxima
  vez que aparezca la misma estructura de columnas.

Segundo grupo, NER asistido por modelo (spec sección 5 + paso 5 del orden
de implementación, ver app/investigation/ner.py):
- `investigation_propose_entities`: el modelo PROPONE entidades sobre texto
  no estructurado de un artefacto YA ingresado -- nunca escribe al grafo.
- `investigation_list_pending_proposals`: lista lo pendiente de confirmar.
- `investigation_confirm_proposal` / `investigation_reject_proposal`: las
  ÚNICAS dos formas de resolver una propuesta -- requieren la decisión
  explícita de Damian, nunca se llaman por iniciativa propia del modelo.

Tercer grupo, exports de mensajería (spec sección 2, paso 6, ver
app/investigation/chat_parser.py):
- `investigation_ingest_whatsapp_export` / `investigation_ingest_telegram_export`:
  determinísticas (sin LLM), un nodo Evento real por mensaje + el
  remitente como Cuenta o Persona según lo que traiga el export.

Cuarto grupo, logs de servidor con detección de formato (spec sección 2,
paso 6, ver app/investigation/server_log_parser.py):
- `investigation_ingest_server_log`: detecta Apache/Nginx (Combined Log
  Format) vs auth.log (SSH) solo, sin que se lo digan -- si no reconoce el
  formato, no adivina, tira error.

Quinto grupo, imágenes -- EXIF + visión (spec sección 2, paso 6, ver
app/investigation/exif_parser.py):
- `investigation_ingest_image`: determinística, sin modelo -- EXIF real
  (fecha de captura, GPS, cámara) hacia un nodo Evento, solo si el EXIF
  trae fecha real (nunca se inventa una).
- `investigation_describe_image`: el modelo de visión describe lo que se
  VE (nunca concluye identidad) -- el resultado es texto suelto, para
  pasarlo después a investigation_propose_entities si hace falta extraer
  entidades de ahí, reusando el mismo pipeline de confirmación de NER.

Sexto grupo, PDF/DOCX -- último parser del paso 6, ver
app/investigation/doc_parser.py:
- `investigation_ingest_document`: determinística, sin modelo -- guarda el
  artefacto y devuelve el texto extraído LISTO para pasar a
  investigation_propose_entities (esta tool no llama a NER por sí sola).

Séptimo grupo, fusión de identidades -- paso 7, ver
app/investigation/fusion.py (detección de comunidades no tiene tool propia:
va directo en el campo `community` de GET /api/investigation/{case_id}/graph,
mismo criterio que centrality/confidence, dato crudo para que la UI decida):
- `investigation_propose_fusion`: el modelo compara DOS nodos puntuales del
  MISMO tipo y propone si parecen la misma entidad -- nunca escribe nada.
- `investigation_list_pending_fusions`, `investigation_confirm_fusion` /
  `investigation_reject_fusion`: confirmar crea una arista mismo_que real
  entre los DOS nodos existentes -- NUNCA los combina en uno.

Octavo y último grupo, export de informe -- paso 8, ver
app/investigation/report_export.py:
- `investigation_export_report`: determinística, sin modelo -- Markdown +
  PDF reales del caso (resumen, grafo renderizado, timeline, tabla de
  entidades, anexo de artefactos con hash, y una sección aparte con todo
  lo generado por el modelo)."""

from __future__ import annotations

import base64
import csv
import io
from pathlib import Path

from .. import audit_log
from ..config import settings
from ..investigation import (
    case_store,
    chat_parser,
    column_mapping as column_mapping_module,
    csv_parser,
    doc_parser,
    exif_parser,
    fusion,
    ner,
    report_export,
    server_log_parser,
)
from ..investigation.models import NodeType
from . import register_tool

_SAMPLE_ROWS_FOR_PROPOSAL = 5


@register_tool(
    name="investigation_create_case",
    description=(
        "Crea un caso nuevo del módulo de investigación (análisis de enlaces y evidencia digital) -- un "
        "directorio propio con su propio repo git, log append-only firmado, y grafo vacío. Usalo antes de "
        "ingestar cualquier artefacto -- todo lo demás del módulo necesita un case_id existente. Recordá el "
        "alcance de este módulo: solo analiza material que Damian YA TIENE legítimamente, nunca sale a buscar "
        "nada por su cuenta."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Identificador corto del caso (se usa como nombre de carpeta, sin espacios)."},
            "titulo": {"type": "string", "description": "Título descriptivo del caso."},
        },
        "required": ["case_id", "titulo"],
    },
)
def investigation_create_case(case_id: str, titulo: str) -> dict:
    arguments = {"case_id": case_id, "titulo": titulo}
    try:
        result = case_store.create_case(settings.investigation_cases_dir, case_id, titulo)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_create_case", arguments=arguments, error=str(exc))
        raise
    audit_log.log_tool_call(target="pc", tool="investigation_create_case", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_propose_column_mapping",
    description=(
        "Le pide al modelo que PROPONGA a qué campo del schema de entidades corresponde cada columna de un "
        "CSV (mirando nombres de columna y valores de ejemplo reales del propio archivo) -- NUNCA decide el "
        "mapeo final ni escribe nada al grafo, solo propone. Mostrale la propuesta a Damian y conseguí su "
        "confirmación (o corrección) explícita ANTES de llamar a investigation_ingest_csv con un "
        "column_mapping -- no asumas que la propuesta es correcta sin que él la confirme."
    ),
    parameters={
        "type": "object",
        "properties": {
            "csv_content": {"type": "string", "description": "Contenido completo del CSV como texto (con encabezado)."},
            "node_type": {
                "type": "string",
                "description": "Tipo de entidad de destino para cada fila (Persona, Cuenta, Dispositivo, Host, Archivo, Transacción, Evento, Organización).",
            },
        },
        "required": ["csv_content", "node_type"],
    },
)
async def investigation_propose_column_mapping(csv_content: str, node_type: str) -> dict:
    arguments = {"node_type": node_type}
    try:
        node_type_enum = NodeType(node_type)
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)
        columns = reader.fieldnames or []
        proposal = await column_mapping_module.propose_mapping(node_type_enum, columns, rows[:_SAMPLE_ROWS_FOR_PROPOSAL])
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_propose_column_mapping", arguments=arguments, error=str(exc))
        raise
    result = {
        "columns": proposal.columns,
        "unmapped_columns": proposal.unmapped_columns,
        "reasoning": proposal.reasoning,
        "note": "Esto es SOLO una propuesta -- mostrasela a Damian y conseguí su confirmación explícita antes de ingestar.",
    }
    audit_log.log_tool_call(target="pc", tool="investigation_propose_column_mapping", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_ingest_csv",
    description=(
        "Ingesta real un CSV a un caso -- guarda el artefacto con hash SHA-256 en el almacén de solo lectura, "
        "crea un nodo por fila nueva (con su arista aparece_en real hacia el archivo de origen, trazable), y "
        "reingestas del mismo archivo solo procesan las filas nuevas. Si NO le pasás 'column_mapping', busca "
        "uno ya confirmado y guardado antes para esta misma estructura de columnas -- si no hay ninguno, "
        "devuelve un error pidiéndote que llames primero a investigation_propose_column_mapping y consigas la "
        "confirmación de Damian. Si SÍ le pasás 'column_mapping' (porque Damian acaba de confirmar uno), lo "
        "usa y lo guarda para la próxima vez que aparezca esta misma estructura."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece esta ingesta (ver investigation_create_case)."},
            "csv_content": {"type": "string", "description": "Contenido completo del CSV como texto (con encabezado)."},
            "original_filename": {"type": "string", "description": "Nombre real del archivo (se guarda como metadata del artefacto)."},
            "node_type": {"type": "string", "description": "Tipo de entidad de destino para cada fila."},
            "column_mapping": {
                "type": "object",
                "description": "Mapeo YA CONFIRMADO por Damian: {columna_csv: campo_del_schema}. Omitilo para reusar un mapeo guardado antes.",
            },
            "defaults": {
                "type": "object",
                "description": "Valores por default para campos del schema que el CSV no trae en ninguna columna (ej. {'plataforma': 'telegram'}).",
            },
        },
        "required": ["case_id", "csv_content", "original_filename", "node_type"],
    },
)
def investigation_ingest_csv(
    case_id: str,
    csv_content: str,
    original_filename: str,
    node_type: str,
    column_mapping: dict | None = None,
    defaults: dict | None = None,
) -> dict:
    arguments = {"case_id": case_id, "original_filename": original_filename, "node_type": node_type, "column_mapping": column_mapping}
    try:
        node_type_enum = NodeType(node_type)
        reader = csv.DictReader(io.StringIO(csv_content))
        columns = reader.fieldnames or []

        effective_mapping = column_mapping
        effective_defaults = defaults or {}
        if effective_mapping is None:
            saved = column_mapping_module.load_saved_mapping(_mappings_dir(case_id), columns)
            if saved is None:
                raise ValueError(
                    "No hay ningún mapeo confirmado guardado para estas columnas todavía -- llamá primero a "
                    "investigation_propose_column_mapping, conseguí la confirmación de Damian, y volvé a "
                    "llamar a esta tool pasando ese column_mapping explícito."
                )
            effective_mapping = saved["column_mapping"]
            effective_defaults = saved.get("defaults", {})
        else:
            column_mapping_module.save_mapping(_mappings_dir(case_id), columns, node_type_enum, effective_mapping, effective_defaults)

        created = csv_parser.ingest_csv(
            cases_dir=settings.investigation_cases_dir, keys_dir=settings.investigation_keys_dir,
            artifact_store_dir=settings.investigation_artifact_store_dir, case_id=case_id,
            csv_bytes=csv_content.encode("utf-8"), original_filename=original_filename,
            node_type=node_type_enum, column_mapping=effective_mapping, defaults=effective_defaults,
            ingested_by="damian",
        )
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_ingest_csv", arguments=arguments, error=str(exc))
        raise
    result = {"nodes_created": len(created), "node_ids": [n.id for n in created]}
    audit_log.log_tool_call(target="pc", tool="investigation_ingest_csv", arguments=arguments, result=result)
    return result


def _mappings_dir(case_id: str) -> Path:
    return Path(settings.investigation_cases_dir) / case_id / "column_mappings"


@register_tool(
    name="investigation_propose_entities",
    description=(
        "Le pide al modelo que PROPONGA entidades (Persona, Cuenta, Dispositivo, Host, Transacción, Evento u "
        "Organización -- nunca Archivo) a partir de un fragmento de texto no estructurado de un artefacto YA "
        "ingresado al caso (ej. texto extraído de un PDF, un mensaje de chat). NUNCA escribe nada al grafo -- "
        "cada propuesta queda 'pendiente' hasta que Damian la confirme o rechace explícitamente con "
        "investigation_confirm_proposal / investigation_reject_proposal. Mostrale SIEMPRE las propuestas "
        "(incluido el texto_fuente exacto de cada una, para que pueda verificarlas) antes de confirmar nada."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece este texto."},
            "texto": {"type": "string", "description": "Fragmento de texto no estructurado a analizar."},
            "artefacto_origen": {"type": "string", "description": "id del Node Archivo ya ingresado del que sale este texto (ver investigation_ingest_csv u otras ingestas)."},
        },
        "required": ["case_id", "texto", "artefacto_origen"],
    },
)
async def investigation_propose_entities(case_id: str, texto: str, artefacto_origen: str) -> dict:
    arguments = {"case_id": case_id, "artefacto_origen": artefacto_origen}
    try:
        result_obj = await ner.propose_entities(texto, artefacto_origen)
        ner.save_proposals(settings.investigation_cases_dir, case_id, result_obj.proposals)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_propose_entities", arguments=arguments, error=str(exc))
        raise
    result = {
        "proposals": [
            {
                "id": p.id, "tipo": p.tipo.value, "campos": p.campos, "texto_fuente": p.texto_fuente,
                "confianza_extraccion": p.confianza_extraccion, "razon": p.razon,
            }
            for p in result_obj.proposals
        ],
        "discarded": result_obj.discarded,
        "note": "Pendientes de confirmación -- mostraselas a Damian y usá investigation_confirm_proposal / investigation_reject_proposal según lo que decida, nunca decidas vos.",
    }
    audit_log.log_tool_call(target="pc", tool="investigation_propose_entities", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_list_pending_proposals",
    description="Lista las propuestas de entidad (NER) todavía pendientes de confirmación en un caso.",
    parameters={
        "type": "object",
        "properties": {"case_id": {"type": "string", "description": "Caso a consultar."}},
        "required": ["case_id"],
    },
)
def investigation_list_pending_proposals(case_id: str) -> dict:
    arguments = {"case_id": case_id}
    try:
        proposals = ner.read_proposals(settings.investigation_cases_dir, case_id, status="pendiente")
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_list_pending_proposals", arguments=arguments, error=str(exc))
        raise
    result = {
        "proposals": [
            {
                "id": p.id, "tipo": p.tipo.value, "campos": p.campos, "texto_fuente": p.texto_fuente,
                "confianza_extraccion": p.confianza_extraccion, "razon": p.razon,
            }
            for p in proposals
        ]
    }
    audit_log.log_tool_call(target="pc", tool="investigation_list_pending_proposals", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_confirm_proposal",
    description=(
        "Confirma una propuesta de entidad (NER) pendiente -- crea el nodo real en el grafo, con su arista de "
        "trazabilidad hacia el artefacto de origen (derivada_por=modelo). SOLO llamala cuando Damian confirmó "
        "explícitamente esa propuesta puntual -- nunca por iniciativa propia."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece la propuesta."},
            "proposal_id": {"type": "string", "description": "id de la propuesta (ver investigation_propose_entities / investigation_list_pending_proposals)."},
        },
        "required": ["case_id", "proposal_id"],
    },
)
def investigation_confirm_proposal(case_id: str, proposal_id: str) -> dict:
    arguments = {"case_id": case_id, "proposal_id": proposal_id}
    try:
        node = ner.confirm_proposal(settings.investigation_cases_dir, settings.investigation_keys_dir, case_id, proposal_id)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_confirm_proposal", arguments=arguments, error=str(exc))
        raise
    result = {"node_id": node.id, "tipo": node.tipo.value}
    audit_log.log_tool_call(target="pc", tool="investigation_confirm_proposal", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_reject_proposal",
    description="Rechaza una propuesta de entidad (NER) pendiente -- no crea ningún nodo, queda registrada como rechazada con el motivo.",
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece la propuesta."},
            "proposal_id": {"type": "string", "description": "id de la propuesta a rechazar."},
            "reason": {"type": "string", "description": "Motivo del rechazo (ej. 'no es una entidad real distinguible', 'confunde dos personas distintas')."},
        },
        "required": ["case_id", "proposal_id", "reason"],
    },
)
def investigation_reject_proposal(case_id: str, proposal_id: str, reason: str) -> dict:
    arguments = {"case_id": case_id, "proposal_id": proposal_id, "reason": reason}
    try:
        rejected = ner.reject_proposal(settings.investigation_cases_dir, settings.investigation_keys_dir, case_id, proposal_id, reason)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_reject_proposal", arguments=arguments, error=str(exc))
        raise
    result = {"id": rejected.id, "status": rejected.status}
    audit_log.log_tool_call(target="pc", tool="investigation_reject_proposal", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_ingest_whatsapp_export",
    description=(
        "Ingesta real un export .txt de WhatsApp (formato Android o iOS) a un caso -- un nodo Evento por "
        "mensaje real (multilínea incluido), el remitente como nodo Persona (WhatsApp no da un id de cuenta "
        "estable, solo nombre de display). Reingestar el MISMO archivo sin cambios no duplica nada. Ojo: un "
        "export nuevo con mensajes agregados es un archivo de hash distinto -- los mensajes viejos se vuelven "
        "a crear (duplicados, cada uno trazable a su propio archivo de origen igual, ver chat_parser.py) -- "
        "avisale a Damian si eso importa para el caso."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece esta ingesta."},
            "txt_content": {"type": "string", "description": "Contenido completo del export .txt de WhatsApp."},
            "original_filename": {"type": "string", "description": "Nombre real del archivo exportado."},
        },
        "required": ["case_id", "txt_content", "original_filename"],
    },
)
def investigation_ingest_whatsapp_export(case_id: str, txt_content: str, original_filename: str) -> dict:
    arguments = {"case_id": case_id, "original_filename": original_filename}
    try:
        created = chat_parser.ingest_whatsapp_export(
            cases_dir=settings.investigation_cases_dir, keys_dir=settings.investigation_keys_dir,
            artifact_store_dir=settings.investigation_artifact_store_dir, case_id=case_id,
            txt_bytes=txt_content.encode("utf-8"), original_filename=original_filename, ingested_by="damian",
        )
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_ingest_whatsapp_export", arguments=arguments, error=str(exc))
        raise
    result = {"nodes_touched": len(created), "node_ids": [n.id for n in created]}
    audit_log.log_tool_call(target="pc", tool="investigation_ingest_whatsapp_export", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_ingest_telegram_export",
    description=(
        "Ingesta real un export .json de Telegram a un caso -- un nodo Evento por mensaje real (se saltean "
        "mensajes de servicio como cambios de nombre de grupo), el remitente como nodo Cuenta si el export "
        "trae from_id (el caso normal), o Persona si no. A diferencia de WhatsApp, Telegram sí trae un id de "
        "chat estable -- reingestar el mismo chat con mensajes nuevos agregados NO duplica los viejos."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece esta ingesta."},
            "json_content": {"type": "string", "description": "Contenido completo del export .json de Telegram."},
            "original_filename": {"type": "string", "description": "Nombre real del archivo exportado."},
        },
        "required": ["case_id", "json_content", "original_filename"],
    },
)
def investigation_ingest_telegram_export(case_id: str, json_content: str, original_filename: str) -> dict:
    arguments = {"case_id": case_id, "original_filename": original_filename}
    try:
        created = chat_parser.ingest_telegram_export(
            cases_dir=settings.investigation_cases_dir, keys_dir=settings.investigation_keys_dir,
            artifact_store_dir=settings.investigation_artifact_store_dir, case_id=case_id,
            json_bytes=json_content.encode("utf-8"), original_filename=original_filename, ingested_by="damian",
        )
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_ingest_telegram_export", arguments=arguments, error=str(exc))
        raise
    result = {"nodes_touched": len(created), "node_ids": [n.id for n in created]}
    audit_log.log_tool_call(target="pc", tool="investigation_ingest_telegram_export", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_ingest_server_log",
    description=(
        "Ingesta real un log de servidor a un caso -- detecta automáticamente si es un access log de "
        "Apache/Nginx (Combined Log Format) o un auth.log de SSH, sin que le digas cuál es. Crea un nodo Host "
        "por IP (dedup real entre archivos distintos -- la misma IP en dos logs resuelve al mismo nodo), un "
        "Evento por línea, y en auth.log también un nodo Cuenta por usuario (acotado al host de origen: "
        "'admin' en el servidor A y 'admin' en el servidor B nunca se confunden). Si el formato no se "
        "reconoce, tira error en vez de adivinar -- no le insistas con el mismo archivo."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece esta ingesta."},
            "log_content": {"type": "string", "description": "Contenido completo del archivo de log."},
            "original_filename": {"type": "string", "description": "Nombre real del archivo de log."},
        },
        "required": ["case_id", "log_content", "original_filename"],
    },
)
def investigation_ingest_server_log(case_id: str, log_content: str, original_filename: str) -> dict:
    arguments = {"case_id": case_id, "original_filename": original_filename}
    try:
        created = server_log_parser.ingest_server_log(
            cases_dir=settings.investigation_cases_dir, keys_dir=settings.investigation_keys_dir,
            artifact_store_dir=settings.investigation_artifact_store_dir, case_id=case_id,
            log_bytes=log_content.encode("utf-8"), original_filename=original_filename, ingested_by="damian",
        )
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_ingest_server_log", arguments=arguments, error=str(exc))
        raise
    result = {"nodes_touched": len(created), "node_ids": [n.id for n in created]}
    audit_log.log_tool_call(target="pc", tool="investigation_ingest_server_log", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_ingest_image",
    description=(
        "Ingesta real una imagen a un caso -- guarda el artefacto con hash SHA-256, y lee su EXIF real "
        "(fecha de captura, cámara, GPS si lo trae) hacia un nodo Evento -- SOLO si el EXIF trae una fecha de "
        "captura real (nunca se inventa una si no está). Esto NO analiza el contenido visual -- para eso está "
        "investigation_describe_image, un paso aparte."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece esta ingesta."},
            "image_base64": {"type": "string", "description": "Contenido de la imagen codificado en base64."},
            "original_filename": {"type": "string", "description": "Nombre real del archivo de imagen."},
        },
        "required": ["case_id", "image_base64", "original_filename"],
    },
)
def investigation_ingest_image(case_id: str, image_base64: str, original_filename: str) -> dict:
    arguments = {"case_id": case_id, "original_filename": original_filename}
    try:
        image_bytes = base64.b64decode(image_base64)
        ingested = exif_parser.ingest_image(
            cases_dir=settings.investigation_cases_dir, keys_dir=settings.investigation_keys_dir,
            artifact_store_dir=settings.investigation_artifact_store_dir, case_id=case_id,
            image_bytes=image_bytes, original_filename=original_filename, ingested_by="damian",
        )
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_ingest_image", arguments=arguments, error=str(exc))
        raise
    result = {
        "archivo_id": ingested["archivo"].id,
        "evento_id": ingested["evento"].id if ingested["evento"] else None,
        "exif": ingested["exif"],
    }
    audit_log.log_tool_call(target="pc", tool="investigation_ingest_image", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_describe_image",
    description=(
        "Le pide al modelo de visión que describa OBJETIVAMENTE lo que se ve en una imagen (personas sin "
        "identificarlas, objetos, texto legible, escena) -- nunca concluye identidad ni especula. Devuelve "
        "texto suelto, nada se escribe al grafo. Si querés extraer entidades de esa descripción (ej. un "
        "cartel con una dirección, un texto visible), pasala a investigation_propose_entities con el "
        "artefacto_origen de la imagen (ver investigation_ingest_image) -- mismo pipeline de confirmación que "
        "NER sobre texto. Si el modelo cargado no soporta imágenes, devuelve description=null -- no insistas "
        "reintentando la misma imagen."
    ),
    parameters={
        "type": "object",
        "properties": {
            "image_base64": {"type": "string", "description": "Contenido de la imagen codificado en base64."},
            "mime_type": {"type": "string", "description": "Tipo MIME de la imagen (ej. 'image/jpeg'). Default image/jpeg."},
        },
        "required": ["image_base64"],
    },
)
async def investigation_describe_image(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    arguments = {"mime_type": mime_type}
    try:
        image_bytes = base64.b64decode(image_base64)
        description = await exif_parser.describe_image_content(image_bytes, mime_type=mime_type)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_describe_image", arguments=arguments, error=str(exc))
        raise
    result = {"description": description}
    audit_log.log_tool_call(target="pc", tool="investigation_describe_image", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_ingest_document",
    description=(
        "Ingesta real un documento PDF o DOCX a un caso -- guarda el artefacto con hash SHA-256 (detecta el "
        "formato por la firma real de los bytes, no por la extensión del nombre) y extrae su texto completo. "
        "Esto NO extrae entidades por sí solo -- pasá el texto devuelto a investigation_propose_entities con "
        "el archivo_id de este resultado si querés una pasada de NER sobre el contenido."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece esta ingesta."},
            "document_base64": {"type": "string", "description": "Contenido del PDF/DOCX codificado en base64."},
            "original_filename": {"type": "string", "description": "Nombre real del archivo."},
        },
        "required": ["case_id", "document_base64", "original_filename"],
    },
)
def investigation_ingest_document(case_id: str, document_base64: str, original_filename: str) -> dict:
    arguments = {"case_id": case_id, "original_filename": original_filename}
    try:
        doc_bytes = base64.b64decode(document_base64)
        ingested = doc_parser.ingest_document(
            cases_dir=settings.investigation_cases_dir, keys_dir=settings.investigation_keys_dir,
            artifact_store_dir=settings.investigation_artifact_store_dir, case_id=case_id,
            doc_bytes=doc_bytes, original_filename=original_filename, ingested_by="damian",
        )
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_ingest_document", arguments=arguments, error=str(exc))
        raise
    result = {"archivo_id": ingested["archivo"].id, "formato": ingested["formato"], "texto": ingested["texto"]}
    audit_log.log_tool_call(target="pc", tool="investigation_ingest_document", arguments=arguments, result=result)
    return result


def _get_node_or_raise(case_id: str, node_id: str):
    nodes = case_store.read_nodes(settings.investigation_cases_dir, case_id)
    node = next((n for n in nodes if n.id == node_id), None)
    if node is None:
        raise ValueError(f"No existe el nodo '{node_id}' en el caso '{case_id}'")
    return node


@register_tool(
    name="investigation_propose_fusion",
    description=(
        "Le pide al modelo que compare DOS nodos puntuales del MISMO tipo y evalúe si parecen la misma "
        "entidad real mencionada de forma distinta en dos fuentes (ej. mismo nombre con variante de "
        "escritura) -- NUNCA escribe nada al grafo, solo propone con una confianza y un motivo. Usala cuando "
        "vos (o Damian) noten dos nodos sospechosos de ser la misma entidad -- no hay un escaneo automático "
        "de todo el grafo, señalás el par puntual. Mostrale la propuesta a Damian y conseguí su confirmación "
        "o rechazo explícito con investigation_confirm_fusion / investigation_reject_fusion."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenecen los dos nodos."},
            "node_a_id": {"type": "string", "description": "id del primer nodo."},
            "node_b_id": {"type": "string", "description": "id del segundo nodo (mismo tipo que el primero)."},
        },
        "required": ["case_id", "node_a_id", "node_b_id"],
    },
)
async def investigation_propose_fusion(case_id: str, node_a_id: str, node_b_id: str) -> dict:
    arguments = {"case_id": case_id, "node_a_id": node_a_id, "node_b_id": node_b_id}
    try:
        node_a = _get_node_or_raise(case_id, node_a_id)
        node_b = _get_node_or_raise(case_id, node_b_id)
        proposal = await fusion.propose_fusion(node_a, node_b)
        fusion.save_proposal(settings.investigation_cases_dir, case_id, proposal)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_propose_fusion", arguments=arguments, error=str(exc))
        raise
    result = {"id": proposal.id, "confianza": proposal.confianza, "razon": proposal.razon}
    audit_log.log_tool_call(target="pc", tool="investigation_propose_fusion", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_list_pending_fusions",
    description="Lista las propuestas de fusión de identidad todavía pendientes de confirmación en un caso.",
    parameters={
        "type": "object",
        "properties": {"case_id": {"type": "string", "description": "Caso a consultar."}},
        "required": ["case_id"],
    },
)
def investigation_list_pending_fusions(case_id: str) -> dict:
    arguments = {"case_id": case_id}
    try:
        proposals = fusion.read_proposals(settings.investigation_cases_dir, case_id, status="pendiente")
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_list_pending_fusions", arguments=arguments, error=str(exc))
        raise
    result = {
        "proposals": [
            {"id": p.id, "node_a_id": p.node_a_id, "node_b_id": p.node_b_id, "confianza": p.confianza, "razon": p.razon}
            for p in proposals
        ]
    }
    audit_log.log_tool_call(target="pc", tool="investigation_list_pending_fusions", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_confirm_fusion",
    description=(
        "Confirma una propuesta de fusión pendiente -- crea una arista mismo_que real entre los DOS nodos "
        "existentes. Los nodos NUNCA se combinan en uno solo (cada uno conserva su proveniencia propia, así "
        "que la fusión se puede retractar más adelante sin perder nada de ninguno). SOLO llamala cuando "
        "Damian confirmó explícitamente esa propuesta puntual."
    ),
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece la propuesta."},
            "proposal_id": {"type": "string", "description": "id de la propuesta de fusión."},
        },
        "required": ["case_id", "proposal_id"],
    },
)
def investigation_confirm_fusion(case_id: str, proposal_id: str) -> dict:
    arguments = {"case_id": case_id, "proposal_id": proposal_id}
    try:
        edge = fusion.confirm_fusion(settings.investigation_cases_dir, settings.investigation_keys_dir, case_id, proposal_id)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_confirm_fusion", arguments=arguments, error=str(exc))
        raise
    result = {"edge_id": edge.id, "origen": edge.origen, "destino": edge.destino}
    audit_log.log_tool_call(target="pc", tool="investigation_confirm_fusion", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_reject_fusion",
    description="Rechaza una propuesta de fusión pendiente -- no crea ninguna arista, queda registrada como rechazada con el motivo.",
    parameters={
        "type": "object",
        "properties": {
            "case_id": {"type": "string", "description": "Caso al que pertenece la propuesta."},
            "proposal_id": {"type": "string", "description": "id de la propuesta de fusión a rechazar."},
            "reason": {"type": "string", "description": "Motivo del rechazo (ej. 'son personas distintas con el mismo nombre')."},
        },
        "required": ["case_id", "proposal_id", "reason"],
    },
)
def investigation_reject_fusion(case_id: str, proposal_id: str, reason: str) -> dict:
    arguments = {"case_id": case_id, "proposal_id": proposal_id, "reason": reason}
    try:
        rejected = fusion.reject_fusion(settings.investigation_cases_dir, settings.investigation_keys_dir, case_id, proposal_id, reason)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_reject_fusion", arguments=arguments, error=str(exc))
        raise
    result = {"id": rejected.id, "status": rejected.status}
    audit_log.log_tool_call(target="pc", tool="investigation_reject_fusion", arguments=arguments, result=result)
    return result


@register_tool(
    name="investigation_export_report",
    description=(
        "Genera y guarda un informe real del caso en Markdown y PDF (resumen, grafo renderizado, timeline, "
        "tabla de entidades con confianza, anexo de artefactos con sus hashes, y una sección aparte con todo "
        "lo generado por el modelo). Ambos archivos quedan en la carpeta 'reports' del caso -- no se "
        "commitean a git (son un derivado regenerable del estado real, no una fuente de verdad nueva)."
    ),
    parameters={
        "type": "object",
        "properties": {"case_id": {"type": "string", "description": "Caso a exportar."}},
        "required": ["case_id"],
    },
)
def investigation_export_report(case_id: str) -> dict:
    arguments = {"case_id": case_id}
    try:
        result_obj = report_export.export_report(settings.investigation_cases_dir, settings.investigation_keys_dir, case_id)
    except Exception as exc:
        audit_log.log_tool_call(target="pc", tool="investigation_export_report", arguments=arguments, error=str(exc))
        raise
    result = {"markdown_path": result_obj["markdown_path"], "pdf_path": result_obj["pdf_path"]}
    audit_log.log_tool_call(target="pc", tool="investigation_export_report", arguments=arguments, result=result)
    return result
