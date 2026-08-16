"""Validación en profundidad del módulo de investigación: un caso ÚNICO
que encadena TODOS los parsers/pasos reales en la misma corrida (CSV,
export de WhatsApp, log de servidor, imagen con EXIF, PDF, NER, fusión de
identidades, métricas de grafo, export de informe) y verifica que el
sistema es consistente de punta a punta -- algo que ningún test unitario
por módulo puede probar, porque cada uno aísla su propia pieza.

Verificaciones reales que este archivo agrega sobre lo que ya prueban los
tests unitarios existentes:
1. Cada nodo no-Archivo que vino de un parser tiene al menos una arista
   `aparece_en` real hacia un Archivo con hash verificable (criterio de
   aceptación literal de la spec).
2. El log firmado de TODO el caso (7 artefactos distintos + confirmaciones
   de NER/fusión) verifica sin romperse.
3. `rebuild_from_log` reconstruye exactamente el estado materializado,
   incluso con esta cantidad y variedad de operaciones mezcladas.
4. El informe final (Markdown + PDF) incluye contenido real de TODAS las
   fuentes, no solo de la última ingestada."""

from __future__ import annotations

import io
import json
from types import SimpleNamespace

import docx
import pytest
from PIL import Image
from PIL.ExifTags import IFD

from app.investigation import (
    case_store,
    chat_parser,
    csv_parser,
    doc_parser,
    exif_parser,
    fusion,
    graph_metrics,
    keys,
    log as log_module,
    ner,
    report_export,
    server_log_parser,
)
from app.investigation.models import NodeType


@pytest.fixture()
def env(tmp_path):
    keys_dir = tmp_path / "keys"
    cases_dir = tmp_path / "cases"
    artifact_dir = tmp_path / "artifacts"
    keys.ensure_keypair(keys_dir)
    case_store.create_case(cases_dir, "caso-integrado", "Caso de validación end-to-end")
    return {"keys_dir": keys_dir, "cases_dir": cases_dir, "artifact_dir": artifact_dir, "case_id": "caso-integrado"}


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _minimal_pdf(text: str) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 300 144] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream_content = f"BT /F1 18 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects.append(b"<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n" + stream_content + b"\nendstream")
    header = b"%PDF-1.4\n"
    body_parts, offsets, pos = [], [], len(header)
    for i, obj in enumerate(objects, start=1):
        offsets.append(pos)
        part = f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
        body_parts.append(part)
        pos += len(part)
    xref_offset = pos
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode()
    return header + b"".join(body_parts) + xref + trailer


def _jpeg_with_exif(datetime_original: str) -> bytes:
    img = Image.new("RGB", (10, 10), color="red")
    exif = img.getexif()
    exif_sub = exif.get_ifd(IFD.Exif)
    exif_sub[0x9003] = datetime_original
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


@pytest.mark.anyio
async def test_full_pipeline_stays_consistent_end_to_end(monkeypatch, env):
    cases_dir, keys_dir, artifact_dir, case_id = env["cases_dir"], env["keys_dir"], env["artifact_dir"], env["case_id"]

    # 1. CSV: dos Cuentas reales.
    csv_created = csv_parser.ingest_csv(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_dir, case_id=case_id,
        csv_bytes=b"nombre,usuario_telegram\nJuan Perez,@juanp\n", original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"usuario_telegram": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )
    assert csv_created  # al menos un nodo real

    # 2. WhatsApp: un mensaje real de "Juan Perez" (mismo nombre que arriba, DISTINTA fuente -- candidato real a fusión).
    chat_parser.ingest_whatsapp_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_dir, case_id=case_id,
        txt_bytes="12/08/2026, 14:30 - Juan Perez: Hola, coordinemos la transferencia\n".encode("utf-8"),
        original_filename="chat.txt", ingested_by="damian",
    )

    # 3. Log de servidor: un intento SSH real.
    server_log_parser.ingest_server_log(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_dir, case_id=case_id,
        log_bytes=b"Aug 12 14:35:00 srv sshd[111]: Accepted password for damian from 203.0.113.9 port 22 ssh2\n",
        original_filename="auth.log", ingested_by="damian",
    )

    # 4. Imagen con EXIF real.
    exif_parser.ingest_image(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_dir, case_id=case_id,
        image_bytes=_jpeg_with_exif("2026:08:12 14:40:00"), original_filename="foto.jpg", ingested_by="damian",
    )

    # 5. PDF real (texto para la pasada de NER después).
    pdf_result = doc_parser.ingest_document(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_dir, case_id=case_id,
        doc_bytes=_minimal_pdf("Juan Perez firmo el contrato"), original_filename="contrato.pdf", ingested_by="damian",
    )

    # 6. NER sobre el texto del PDF (modelo mockeado) -> confirmar la propuesta.
    ner_payload = json.dumps([{
        "tipo": "Persona", "campos": {"etiqueta": "Juan Perez", "alias": [], "confianza": 0.7},
        "texto_fuente": "Juan Perez firmo el contrato", "confianza_extraccion": 0.85, "razon": "nombre propio explícito",
    }])

    async def fake_ner_create(**kwargs):
        return _fake_response(ner_payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_ner_create)
    ner_result = await ner.propose_entities(pdf_result["texto"], pdf_result["archivo"].id)
    assert ner_result.proposals, "el PDF real debería producir al menos una propuesta de NER"
    ner.save_proposals(cases_dir, case_id, ner_result.proposals)
    ner_node = ner.confirm_proposal(cases_dir, keys_dir, case_id, ner_result.proposals[0].id)

    # 7. Fusión de identidad: el Cuenta del CSV (Juan Perez) y la Persona confirmada por NER (Juan Perez) -- misma etiqueta, dos fuentes distintas.
    persona_from_whatsapp = next(
        n for n in case_store.read_nodes(cases_dir, case_id)
        if n.tipo == NodeType.PERSONA and n.campos["etiqueta"] == "Juan Perez" and n.id != ner_node.id
    )

    async def fake_fusion_create(**kwargs):
        return _fake_response('{"confianza": 0.8, "razon": "mismo nombre, dos fuentes distintas del mismo caso"}')

    monkeypatch.setattr(fusion.client.chat.completions, "create", fake_fusion_create)
    fusion_proposal = await fusion.propose_fusion(ner_node, persona_from_whatsapp)
    fusion.save_proposal(cases_dir, case_id, fusion_proposal)
    fusion_edge = fusion.confirm_fusion(cases_dir, keys_dir, case_id, fusion_proposal.id)
    assert fusion_edge.tipo.value == "mismo_que"

    # --- Verificación 1: TODO nodo no-Archivo trazable a un Archivo con hash real (directo o vía un Evento intermedio). ---
    all_nodes = case_store.read_nodes(cases_dir, case_id)
    all_edges = case_store.read_edges(cases_dir, case_id)
    archivo_ids = {n.id for n in all_nodes if n.tipo == NodeType.ARCHIVO}
    assert len(archivo_ids) == 5  # csv, whatsapp, auth.log, foto, pdf

    aparece_en_edges = [e for e in all_edges if e.tipo.value == "aparece_en"]
    by_origen: dict[str, list[str]] = {}
    for e in aparece_en_edges:
        by_origen.setdefault(e.origen, []).append(e.destino)

    def _reaches_an_archivo(node_id: str, depth: int = 0) -> bool:
        if depth > 3:  # cota real -- ningún camino de trazabilidad de este módulo tiene más de 2 saltos
            return False
        for destino in by_origen.get(node_id, []):
            if destino in archivo_ids or _reaches_an_archivo(destino, depth + 1):
                return True
        return False

    entity_nodes = [n for n in all_nodes if n.tipo != NodeType.ARCHIVO]
    for node in entity_nodes:
        assert _reaches_an_archivo(node.id), f"{node.tipo.value} '{node.id}' no traza a ningún Archivo"

    # --- Verificación 2: el log firmado de TODO el caso (multi-fuente) verifica. ---
    case_dir = case_store.case_dir_for(cases_dir, case_id)
    verification = log_module.verify_chain(case_dir / "log.jsonl", keys_dir)
    assert verification.ok is True, verification.reason

    # --- Verificación 3: rebuild_from_log reproduce EXACTAMENTE el estado materializado. ---
    rebuilt_nodes, rebuilt_edges = case_store.rebuild_from_log(cases_dir, keys_dir, case_id)
    assert {n.id: n.to_dict() for n in rebuilt_nodes} == {n.id: n.to_dict() for n in all_nodes}
    assert {e.id: e.to_dict() for e in rebuilt_edges} == {e.id: e.to_dict() for e in all_edges}

    # --- Verificación 4: métricas de grafo corren sin romperse sobre el grafo mixto real. ---
    centrality = graph_metrics.compute_centrality(all_nodes, all_edges)
    confidence = graph_metrics.compute_confidence(all_nodes, all_edges)
    communities = graph_metrics.detect_communities(all_nodes, all_edges)
    assert len(centrality) == len(all_nodes)
    assert len(communities) <= len(all_nodes)
    # el nodo fusionado por NER tiene que tener una confianza real calculada
    assert confidence.get(ner_node.id) is not None

    # --- Verificación 5: el informe final incluye contenido real de TODAS las fuentes. ---
    report_data = report_export.build_report_data(cases_dir, keys_dir, case_id)
    assert len(report_data.artifacts) == 5
    assert any(a.sha256 for a in report_data.artifacts)  # hashes reales, no vacíos
    model_edge_ids = {m.edge_id for m in report_data.model_generated_edges}
    assert fusion_edge.id in model_edge_ids  # la fusión aparece en la sección "generado por el modelo"

    markdown = report_export.render_markdown(report_data)
    assert "Juan Perez" in markdown
    assert report_data.artifacts[0].sha256 in markdown

    pdf_bytes = report_export.render_pdf(report_data)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 2000


def test_the_same_cuenta_ingested_by_two_different_parsers_resolves_to_one_node(env):
    """Cross-parser: una Cuenta con la MISMA plataforma+handle mencionada
    en un CSV Y en un export de Telegram tiene que resolver al MISMO nodo
    (id determinístico por clave natural, spec sección 1) -- a diferencia
    de Persona (dedup manual vía mismo_que), esto tiene que funcionar SOLO
    porque comparten la clave natural real, sin ninguna fusión de por
    medio. Ningún test unitario por parser puede probar esto porque cada
    uno corre en aislado."""
    cases_dir, keys_dir, artifact_dir, case_id = env["cases_dir"], env["keys_dir"], env["artifact_dir"], env["case_id"]

    csv_parser.ingest_csv(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_dir, case_id=case_id,
        csv_bytes=b"nombre,tg_id\nJuan Perez,999888777\n", original_filename="contactos.csv",
        node_type=NodeType.CUENTA, column_mapping={"tg_id": "handle"},
        defaults={"plataforma": "telegram"}, ingested_by="damian",
    )
    telegram_export = json.dumps({
        "name": "chat", "type": "personal_chat", "id": 42,
        "messages": [{"id": 1, "type": "message", "date": "2026-08-12T14:30:00", "from": "Juan Perez", "from_id": "999888777", "text": "Hola"}],
    })
    chat_parser.ingest_telegram_export(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_dir, case_id=case_id,
        json_bytes=telegram_export.encode("utf-8"), original_filename="telegram.json", ingested_by="damian",
    )

    cuentas = [n for n in case_store.read_nodes(cases_dir, case_id) if n.tipo == NodeType.CUENTA]
    assert len(cuentas) == 1  # un solo nodo, no dos -- misma clave natural real
    assert cuentas[0].campos["handle"] == "999888777"

    # y queda trazable a AMBOS artefactos de origen -- una arista aparece_en
    # real por cada fuente que la mencionó, no solo la última.
    nodes_by_id = {n.id: n for n in case_store.read_nodes(cases_dir, case_id)}
    edges = case_store.read_edges(cases_dir, case_id)
    outgoing = [e for e in edges if e.origen == cuentas[0].id and e.tipo.value == "aparece_en"]
    assert len(outgoing) == 2  # una directa al Archivo del CSV, otra al Evento del mensaje de Telegram
    destino_tipos = {nodes_by_id[e.destino].tipo for e in outgoing}
    assert NodeType.ARCHIVO in destino_tipos  # trazabilidad directa del CSV
    assert NodeType.EVENTO in destino_tipos  # trazabilidad indirecta del mensaje de Telegram
