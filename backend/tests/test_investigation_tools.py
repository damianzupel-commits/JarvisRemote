"""Tests de app/tools/investigation.py -- las tools reales que exponen el
módulo de investigación al chat. Las llamadas al modelo (column_mapping y
ner) se mockean, mismo criterio que el resto del proyecto; create_case/
ingest_csv/confirm_proposal/reject_proposal son deterministicas y se
prueban reales (git real, archivos reales, log firmado real)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import audit_log
from app.tools import investigation


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(investigation.settings, "investigation_cases_dir", str(tmp_path / "cases"))
    monkeypatch.setattr(investigation.settings, "investigation_artifact_store_dir", str(tmp_path / "artifacts"))
    monkeypatch.setattr(investigation.settings, "investigation_keys_dir", str(tmp_path / "keys"))


def _fake_response(content: str):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_create_case_tool_creates_a_real_case():
    result = investigation.investigation_create_case("caso-1", "Caso de prueba")

    assert result["id"] == "caso-1"
    assert result["titulo"] == "Caso de prueba"


def test_create_case_tool_logs_to_audit_log():
    investigation.investigation_create_case("caso-audit", "x")

    entries = audit_log.read_entries(target="pc", tool="investigation_create_case")
    assert entries
    assert entries[-1]["ok"] is True


@pytest.mark.anyio
async def test_propose_column_mapping_tool_parses_csv_and_calls_the_model(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response('{"columns": {"usuario": "handle"}, "reasoning": "coincide"}')

    monkeypatch.setattr(investigation.column_mapping_module.client.chat.completions, "create", fake_create)

    result = await investigation.investigation_propose_column_mapping(
        "usuario,otra\n@juanp,x\n", "Cuenta"
    )

    assert result["columns"] == {"usuario": "handle"}
    user_msg = captured["messages"][1]["content"]
    assert "@juanp" in user_msg


@pytest.mark.anyio
async def test_propose_column_mapping_never_writes_anything(monkeypatch, tmp_path):
    async def fake_create(**kwargs):
        return _fake_response('{"columns": {"usuario": "handle"}, "reasoning": "x"}')

    monkeypatch.setattr(investigation.column_mapping_module.client.chat.completions, "create", fake_create)

    await investigation.investigation_propose_column_mapping("usuario\n@juanp\n", "Cuenta")

    # No debe haber guardado ningun mapeo -- solo propone.
    investigation.investigation_create_case("caso-1", "x")
    saved = investigation.column_mapping_module.load_saved_mapping(
        investigation._mappings_dir("caso-1"), ["usuario"]
    )
    assert saved is None


def test_ingest_csv_without_a_mapping_and_none_saved_raises_a_clear_error():
    investigation.investigation_create_case("caso-1", "x")

    with pytest.raises(ValueError, match="investigation_propose_column_mapping"):
        investigation.investigation_ingest_csv(
            case_id="caso-1", csv_content="usuario\n@juanp\n", original_filename="c.csv", node_type="Cuenta",
        )


def test_ingest_csv_with_explicit_mapping_ingests_and_saves_it_for_reuse():
    investigation.investigation_create_case("caso-1", "x")

    result = investigation.investigation_ingest_csv(
        case_id="caso-1", csv_content="usuario\n@juanp\n", original_filename="c.csv", node_type="Cuenta",
        column_mapping={"usuario": "handle"}, defaults={"plataforma": "telegram"},
    )

    assert result["nodes_created"] == 1

    saved = investigation.column_mapping_module.load_saved_mapping(
        investigation._mappings_dir("caso-1"), ["usuario"]
    )
    assert saved is not None
    assert saved["column_mapping"] == {"usuario": "handle"}


def test_ingest_csv_reuses_a_previously_confirmed_mapping_without_needing_it_again():
    investigation.investigation_create_case("caso-1", "x")
    investigation.investigation_ingest_csv(
        case_id="caso-1", csv_content="usuario\n@juanp\n", original_filename="c.csv", node_type="Cuenta",
        column_mapping={"usuario": "handle"}, defaults={"plataforma": "telegram"},
    )

    # Segunda llamada, SIN pasar column_mapping -- distinto archivo, misma estructura de columnas.
    result = investigation.investigation_ingest_csv(
        case_id="caso-1", csv_content="usuario\n@marial\n", original_filename="c2.csv", node_type="Cuenta",
    )

    assert result["nodes_created"] == 1


def test_ingest_csv_tool_logs_errors_to_audit_log():
    with pytest.raises(Exception):
        investigation.investigation_ingest_csv(
            case_id="no-existe", csv_content="usuario\n@juanp\n", original_filename="c.csv", node_type="Cuenta",
            column_mapping={"usuario": "handle"},
        )

    entries = audit_log.read_entries(target="pc", tool="investigation_ingest_csv")
    assert entries
    assert entries[-1]["ok"] is False


def _make_archivo_node(case_id: str) -> str:
    from app.investigation import case_store
    from app.investigation.models import make_archivo

    node = make_archivo(nombre="chat.txt", sha256="c" * 64, tamano=10, mime="text/plain")
    case_store.add_node(investigation.settings.investigation_cases_dir, investigation.settings.investigation_keys_dir, case_id, node)
    return node.id


@pytest.mark.anyio
async def test_propose_entities_tool_saves_proposals_as_pending(monkeypatch):
    investigation.investigation_create_case("caso-1", "x")
    archivo_id = _make_archivo_node("caso-1")
    payload = (
        '[{"tipo": "Persona", "campos": {"etiqueta": "Juan", "alias": [], "confianza": 0.6}, '
        '"texto_fuente": "Juan dijo algo", "confianza_extraccion": 0.8, "razon": "nombre propio"}]'
    )

    async def fake_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(investigation.ner.client.chat.completions, "create", fake_create)

    result = await investigation.investigation_propose_entities("caso-1", "Juan dijo algo importante", archivo_id)

    assert len(result["proposals"]) == 1
    assert result["proposals"][0]["tipo"] == "Persona"

    pending = investigation.investigation_list_pending_proposals("caso-1")
    assert len(pending["proposals"]) == 1


def test_confirm_proposal_tool_creates_a_real_node():
    investigation.investigation_create_case("caso-1", "x")
    archivo_id = _make_archivo_node("caso-1")
    from app.investigation import ner as ner_module

    ner_module.save_proposals(
        investigation.settings.investigation_cases_dir, "caso-1",
        [ner_module.EntityProposal(
            id="prop-x", tipo=investigation.NodeType.PERSONA,
            campos={"etiqueta": "Juan", "alias": [], "confianza": 0.6},
            texto_fuente="Juan dijo algo", confianza_extraccion=0.8, razon="x",
            artefacto_origen=archivo_id, status="pendiente", created_at="2026-08-12T00:00:00+00:00",
        )],
    )

    result = investigation.investigation_confirm_proposal("caso-1", "prop-x")

    assert result["tipo"] == "Persona"

    entries = audit_log.read_entries(target="pc", tool="investigation_confirm_proposal")
    assert entries[-1]["ok"] is True


def test_reject_proposal_tool_does_not_create_a_node():
    investigation.investigation_create_case("caso-1", "x")
    archivo_id = _make_archivo_node("caso-1")
    from app.investigation import ner as ner_module

    ner_module.save_proposals(
        investigation.settings.investigation_cases_dir, "caso-1",
        [ner_module.EntityProposal(
            id="prop-y", tipo=investigation.NodeType.PERSONA,
            campos={"etiqueta": "Juan", "alias": [], "confianza": 0.6},
            texto_fuente="Juan dijo algo", confianza_extraccion=0.8, razon="x",
            artefacto_origen=archivo_id, status="pendiente", created_at="2026-08-12T00:00:00+00:00",
        )],
    )

    result = investigation.investigation_reject_proposal("caso-1", "prop-y", "no es una entidad real")

    assert result["status"] == "rechazado"
    pending = investigation.investigation_list_pending_proposals("caso-1")
    assert pending["proposals"] == []


def test_ingest_whatsapp_export_tool_creates_real_nodes():
    investigation.investigation_create_case("caso-1", "x")
    txt_content = "12/08/2026, 14:30 - Juan Perez: Hola\n"

    result = investigation.investigation_ingest_whatsapp_export("caso-1", txt_content, "chat.txt")

    assert result["nodes_touched"] == 2  # Persona + Evento
    from app.investigation import case_store
    nodes = case_store.read_nodes(investigation.settings.investigation_cases_dir, "caso-1")
    assert any(n.tipo == investigation.NodeType.EVENTO for n in nodes)


def test_ingest_whatsapp_export_tool_logs_to_audit_log():
    investigation.investigation_create_case("caso-1", "x")

    investigation.investigation_ingest_whatsapp_export("caso-1", "12/08/2026, 14:30 - Juan: Hola\n", "chat.txt")

    entries = audit_log.read_entries(target="pc", tool="investigation_ingest_whatsapp_export")
    assert entries[-1]["ok"] is True


def test_ingest_telegram_export_tool_creates_real_nodes():
    import json

    investigation.investigation_create_case("caso-1", "x")
    export = json.dumps({
        "name": "chat", "type": "personal_chat", "id": 1,
        "messages": [{"id": 1, "type": "message", "date": "2026-08-12T14:30:00", "from": "Juan Perez", "from_id": "user1", "text": "Hola"}],
    })

    result = investigation.investigation_ingest_telegram_export("caso-1", export, "telegram.json")

    assert result["nodes_touched"] == 2  # Cuenta + Evento


def test_ingest_telegram_export_tool_logs_errors_to_audit_log():
    with pytest.raises(Exception):
        investigation.investigation_ingest_telegram_export("no-existe", "not json", "telegram.json")

    entries = audit_log.read_entries(target="pc", tool="investigation_ingest_telegram_export")
    assert entries[-1]["ok"] is False


def test_ingest_server_log_tool_detects_format_and_creates_nodes():
    investigation.investigation_create_case("caso-1", "x")
    access_log = '192.168.1.10 - - [12/Aug/2026:14:30:00 +0000] "GET /index.html HTTP/1.1" 200 1234 "-" "Mozilla/5.0"\n'

    result = investigation.investigation_ingest_server_log("caso-1", access_log, "access.log")

    assert result["nodes_touched"] == 2  # Host + Evento


def test_ingest_server_log_tool_raises_a_clear_error_for_unrecognized_format():
    investigation.investigation_create_case("caso-1", "x")

    with pytest.raises(ValueError, match="No pude reconocer el formato"):
        investigation.investigation_ingest_server_log("caso-1", "no es un log valido\n", "mystery.log")

    entries = audit_log.read_entries(target="pc", tool="investigation_ingest_server_log")
    assert entries[-1]["ok"] is False


def _synthetic_jpeg_base64() -> str:
    import base64
    import io
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_ingest_image_tool_creates_a_real_archivo_node():
    investigation.investigation_create_case("caso-1", "x")

    result = investigation.investigation_ingest_image("caso-1", _synthetic_jpeg_base64(), "foto.jpg")

    assert result["archivo_id"]
    assert result["evento_id"] is None  # imagen sintética sin EXIF -- ningun Evento inventado


def test_ingest_image_tool_logs_to_audit_log():
    investigation.investigation_create_case("caso-1", "x")

    investigation.investigation_ingest_image("caso-1", _synthetic_jpeg_base64(), "foto.jpg")

    entries = audit_log.read_entries(target="pc", tool="investigation_ingest_image")
    assert entries[-1]["ok"] is True


@pytest.mark.anyio
async def test_describe_image_tool_returns_the_model_description(monkeypatch):
    async def fake_create(**kwargs):
        return _fake_response("Se ve una habitación vacía.")

    monkeypatch.setattr(investigation.exif_parser.client.chat.completions, "create", fake_create)

    result = await investigation.investigation_describe_image(_synthetic_jpeg_base64())

    assert result["description"] == "Se ve una habitación vacía."


@pytest.mark.anyio
async def test_describe_image_tool_returns_null_description_when_model_is_not_vl(monkeypatch):
    async def failing_create(**kwargs):
        raise RuntimeError("modelo actual no soporta imágenes")

    monkeypatch.setattr(investigation.exif_parser.client.chat.completions, "create", failing_create)

    result = await investigation.investigation_describe_image(_synthetic_jpeg_base64())

    assert result["description"] is None


def _synthetic_pdf_base64(text: str = "texto de prueba") -> str:
    import base64

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 300 144] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream_content = f"BT /F1 18 Tf 10 100 Td ({text}) Tj ET".encode("latin-1")
    objects.append(
        b"<< /Length " + str(len(stream_content)).encode() + b" >>\nstream\n" + stream_content + b"\nendstream"
    )
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
    pdf_bytes = header + b"".join(body_parts) + xref + trailer
    return base64.b64encode(pdf_bytes).decode("ascii")


def test_ingest_document_tool_extracts_real_text_from_a_pdf():
    investigation.investigation_create_case("caso-1", "x")

    result = investigation.investigation_ingest_document("caso-1", _synthetic_pdf_base64("Juan Perez"), "informe.pdf")

    assert result["formato"] == "pdf"
    assert "Juan Perez" in result["texto"]
    assert result["archivo_id"]


def test_ingest_document_tool_raises_a_clear_error_for_unrecognized_format():
    import base64

    investigation.investigation_create_case("caso-1", "x")

    with pytest.raises(ValueError, match="No pude reconocer el formato"):
        investigation.investigation_ingest_document(
            "caso-1", base64.b64encode(b"no es un documento valido").decode("ascii"), "mystery.pdf",
        )

    entries = audit_log.read_entries(target="pc", tool="investigation_ingest_document")
    assert entries[-1]["ok"] is False


@pytest.mark.anyio
async def test_propose_fusion_tool_creates_a_real_pending_proposal(monkeypatch):
    from app.investigation import case_store as case_store_module
    from app.investigation.models import make_persona

    investigation.investigation_create_case("caso-1", "x")
    a = make_persona(etiqueta="Juan Perez", confianza=0.6)
    b = make_persona(etiqueta="J. Perez", confianza=0.6)
    case_store_module.add_node(investigation.settings.investigation_cases_dir, investigation.settings.investigation_keys_dir, "caso-1", a)
    case_store_module.add_node(investigation.settings.investigation_cases_dir, investigation.settings.investigation_keys_dir, "caso-1", b)

    async def fake_create(**kwargs):
        return _fake_response('{"confianza": 0.8, "razon": "misma persona, variante de nombre"}')

    monkeypatch.setattr(investigation.fusion.client.chat.completions, "create", fake_create)

    result = await investigation.investigation_propose_fusion("caso-1", a.id, b.id)

    assert result["confianza"] == 0.8
    pending = investigation.investigation_list_pending_fusions("caso-1")
    assert len(pending["proposals"]) == 1


def test_confirm_fusion_tool_creates_a_real_edge_without_merging_nodes():
    from app.investigation import case_store as case_store_module, fusion as fusion_module
    from app.investigation.models import make_persona

    investigation.investigation_create_case("caso-1", "x")
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    case_store_module.add_node(investigation.settings.investigation_cases_dir, investigation.settings.investigation_keys_dir, "caso-1", a)
    case_store_module.add_node(investigation.settings.investigation_cases_dir, investigation.settings.investigation_keys_dir, "caso-1", b)
    fusion_module.save_proposal(
        investigation.settings.investigation_cases_dir, "caso-1",
        fusion_module.FusionProposal(
            id="fusion-x", node_a_id=a.id, node_b_id=b.id, confianza=0.8, razon="x",
            status="pendiente", created_at="2026-08-12T00:00:00+00:00",
        ),
    )

    result = investigation.investigation_confirm_fusion("caso-1", "fusion-x")

    assert result["origen"] == a.id
    assert result["destino"] == b.id
    nodes = case_store_module.read_nodes(investigation.settings.investigation_cases_dir, "caso-1")
    assert len(nodes) == 2  # los dos siguen existiendo, ninguno se fusiono en el otro


def test_reject_fusion_tool_does_not_create_an_edge():
    from app.investigation import case_store as case_store_module, fusion as fusion_module
    from app.investigation.models import make_persona

    investigation.investigation_create_case("caso-1", "x")
    a = make_persona(etiqueta="a", confianza=0.5)
    b = make_persona(etiqueta="b", confianza=0.5)
    case_store_module.add_node(investigation.settings.investigation_cases_dir, investigation.settings.investigation_keys_dir, "caso-1", a)
    case_store_module.add_node(investigation.settings.investigation_cases_dir, investigation.settings.investigation_keys_dir, "caso-1", b)
    fusion_module.save_proposal(
        investigation.settings.investigation_cases_dir, "caso-1",
        fusion_module.FusionProposal(
            id="fusion-y", node_a_id=a.id, node_b_id=b.id, confianza=0.8, razon="x",
            status="pendiente", created_at="2026-08-12T00:00:00+00:00",
        ),
    )

    result = investigation.investigation_reject_fusion("caso-1", "fusion-y", "personas distintas")

    assert result["status"] == "rechazado"
    assert case_store_module.read_edges(investigation.settings.investigation_cases_dir, "caso-1") == []


def test_export_report_tool_writes_real_files():
    from pathlib import Path

    investigation.investigation_create_case("caso-1", "x")

    result = investigation.investigation_export_report("caso-1")

    assert Path(result["markdown_path"]).is_file()
    assert Path(result["pdf_path"]).is_file()


def test_export_report_tool_logs_errors_to_audit_log():
    with pytest.raises(Exception):
        investigation.investigation_export_report("no-existe")

    entries = audit_log.read_entries(target="pc", tool="investigation_export_report")
    assert entries[-1]["ok"] is False
