"""Tests de app/investigation/exif_parser.py (paso 6, EXIF + descripción
visual). Imágenes 100% sintéticas generadas con Pillow (nunca una foto
real de nadie) -- EXIF real escrito y vuelto a leer, no mockeado. El
llamado al modelo de visión SÍ se mockea (mismo criterio que el resto del
proyecto para llamadas al LLM)."""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest
from PIL import Image
from PIL.ExifTags import IFD

from app.investigation import case_store, exif_parser, keys, ner
from app.investigation.models import NodeType


@pytest.fixture()
def keys_dir(tmp_path):
    d = tmp_path / "keys"
    keys.ensure_keypair(d)
    return d


@pytest.fixture()
def cases_dir(tmp_path):
    d = tmp_path / "cases"
    case_store.create_case(d, "caso-1", "Caso de prueba")
    return d


@pytest.fixture()
def artifact_store_dir(tmp_path):
    return tmp_path / "artifacts"


def _make_jpeg_with_exif(*, datetime_original: str | None = None, gps: tuple[float, float] | None = None,
                          make: str | None = None, model: str | None = None) -> bytes:
    img = Image.new("RGB", (10, 10), color="red")
    exif = img.getexif()
    if make:
        exif[0x010F] = make
    if model:
        exif[0x0110] = model
    if datetime_original:
        exif_sub = exif.get_ifd(IFD.Exif)
        exif_sub[0x9003] = datetime_original
    if gps:
        lat, lon = gps
        gps_ifd = exif.get_ifd(IFD.GPSInfo)
        gps_ifd[1] = "N" if lat >= 0 else "S"
        gps_ifd[2] = (abs(lat), 0.0, 0.0)
        gps_ifd[3] = "E" if lon >= 0 else "W"
        gps_ifd[4] = (abs(lon), 0.0, 0.0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _make_jpeg_without_exif() -> bytes:
    img = Image.new("RGB", (10, 10), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _fake_response(content):
    message = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


# --- extract_exif_metadata -------------------------------------------------------

def test_extract_exif_metadata_returns_empty_dict_for_image_without_exif():
    assert exif_parser.extract_exif_metadata(_make_jpeg_without_exif()) == {}


def test_extract_exif_metadata_reads_real_camera_and_datetime():
    data = _make_jpeg_with_exif(datetime_original="2026:08:12 14:30:00", make="Test Make", model="Test Camera")

    exif = exif_parser.extract_exif_metadata(data)

    assert exif["make"] == "Test Make"
    assert exif["model"] == "Test Camera"
    assert exif["datetime_original_raw"] == "2026:08:12 14:30:00"


def test_extract_exif_metadata_reads_real_gps_coordinates():
    data = _make_jpeg_with_exif(gps=(-34.6, -58.4))

    exif = exif_parser.extract_exif_metadata(data)

    assert exif["gps_lat"] == pytest.approx(-34.6, abs=0.01)
    assert exif["gps_lon"] == pytest.approx(-58.4, abs=0.01)


def test_exif_datetime_to_iso_does_not_shift_the_day():
    """Bug real encontrado probando esto contra dateutil directo: pasarle
    '2026:08:12 14:30:00' (formato nativo EXIF) a dateutil.parser.parse
    daba el día 13, no el 12 -- por eso esto convierte a ISO real ANTES de
    normalizar, sin pasar por la heurística de dateutil para nada."""
    assert exif_parser._exif_datetime_to_iso("2026:08:12 14:30:00") == "2026-08-12 14:30:00"


# --- ingest_image ------------------------------------------------------------------

def test_ingest_image_rejects_a_corrupt_or_empty_file_with_a_clear_error(cases_dir, keys_dir, artifact_store_dir):
    """Bug real (edge case) encontrado en testing adversarial (2026-08-13):
    bytes que no son una imagen real (o un archivo vacío) tiraban un
    UnidentifiedImageError crudo de Pillow, con un repr de objeto BytesIO en
    el mensaje en vez del nombre real del archivo problemático."""
    with pytest.raises(ValueError, match="corrupta.jpg"):
        exif_parser.ingest_image(
            cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
            image_bytes=b"esto no es una imagen de verdad", original_filename="corrupta.jpg", ingested_by="damian",
        )


def test_ingest_image_always_creates_an_archivo_node(cases_dir, keys_dir, artifact_store_dir):
    result = exif_parser.ingest_image(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        image_bytes=_make_jpeg_without_exif(), original_filename="foto.jpg", ingested_by="damian",
    )

    assert result["archivo"].tipo == NodeType.ARCHIVO
    assert result["evento"] is None  # sin EXIF, sin fecha -- no se inventa un Evento


def test_ingest_image_creates_evento_when_exif_has_a_real_datetime(cases_dir, keys_dir, artifact_store_dir):
    data = _make_jpeg_with_exif(datetime_original="2026:08:12 14:30:00", make="Acme", model="X100", gps=(-34.6, -58.4))

    result = exif_parser.ingest_image(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        image_bytes=data, original_filename="foto.jpg", ingested_by="damian",
    )

    evento = result["evento"]
    assert evento is not None
    assert evento.campos["timestamp_utc"].startswith("2026-08-12T14:30:00")
    assert "Acme" in evento.campos["descripcion"]
    assert "-34.6" in evento.campos["descripcion"]
    assert evento.campos["fuente"] == "exif"


def test_ingest_image_persists_both_nodes_to_the_case(cases_dir, keys_dir, artifact_store_dir):
    data = _make_jpeg_with_exif(datetime_original="2026:08:12 14:30:00")

    exif_parser.ingest_image(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        image_bytes=data, original_filename="foto.jpg", ingested_by="damian",
    )

    nodes = case_store.read_nodes(cases_dir, "caso-1")
    assert any(n.tipo == NodeType.ARCHIVO for n in nodes)
    assert any(n.tipo == NodeType.EVENTO for n in nodes)


def test_ingest_image_creates_a_real_traceability_edge_from_evento_to_archivo(cases_dir, keys_dir, artifact_store_dir):
    """Bug real encontrado con la validación end-to-end del módulo: a
    diferencia de csv_parser/chat_parser/server_log_parser, el Evento
    quedaba sin ninguna arista aparece_en hacia su Archivo de origen --
    criterio de aceptación de la spec violado en silencio."""
    data = _make_jpeg_with_exif(datetime_original="2026:08:12 14:30:00")

    result = exif_parser.ingest_image(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        image_bytes=data, original_filename="foto.jpg", ingested_by="damian",
    )

    edges = case_store.read_edges(cases_dir, "caso-1")
    traceability = next((e for e in edges if e.tipo.value == "aparece_en"), None)
    assert traceability is not None
    assert traceability.origen == result["evento"].id
    assert traceability.destino == result["archivo"].id


# --- describe_image_content ---------------------------------------------------------

@pytest.mark.anyio
async def test_describe_image_content_sends_the_image_as_a_data_url(monkeypatch):
    captured = {}

    async def fake_create(**kwargs):
        captured.update(kwargs)
        return _fake_response("Se ve una habitación vacía con una silla.")

    monkeypatch.setattr(exif_parser.client.chat.completions, "create", fake_create)

    description = await exif_parser.describe_image_content(b"fake-image-bytes", mime_type="image/png")

    assert description == "Se ve una habitación vacía con una silla."
    user_content = captured["messages"][1]["content"]
    assert user_content[0]["type"] == "image_url"
    assert user_content[0]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.anyio
async def test_describe_image_content_returns_none_when_the_model_is_not_vision_capable(monkeypatch):
    async def failing_create(**kwargs):
        raise RuntimeError("el modelo cargado no soporta contenido de imagen")

    monkeypatch.setattr(exif_parser.client.chat.completions, "create", failing_create)

    description = await exif_parser.describe_image_content(b"fake-image-bytes")

    assert description is None


# --- integración real con el pipeline de NER ya existente ---------------------------

@pytest.mark.anyio
async def test_a_vision_description_can_be_fed_into_the_existing_ner_pipeline(monkeypatch, cases_dir, keys_dir, artifact_store_dir):
    """La descripción del modelo no tiene su propio mecanismo de
    confirmación -- reusa ner.propose_entities/save_proposals, que ya
    exige confirmación humana antes de escribir cualquier cosa al grafo."""
    image_result = exif_parser.ingest_image(
        cases_dir=cases_dir, keys_dir=keys_dir, artifact_store_dir=artifact_store_dir, case_id="caso-1",
        image_bytes=_make_jpeg_without_exif(), original_filename="foto.jpg", ingested_by="damian",
    )
    archivo_id = image_result["archivo"].id

    async def fake_vision_create(**kwargs):
        return _fake_response("Se ve una persona con una remera roja parada junto a un cartel que dice 'Calle Falsa 123'.")

    monkeypatch.setattr(exif_parser.client.chat.completions, "create", fake_vision_create)
    description = await exif_parser.describe_image_content(_make_jpeg_without_exif())

    payload = (
        '[{"tipo": "Host", "campos": {"ip_o_dominio": "Calle Falsa 123", "asn": null, "geolocalizacion_declarada": null}, '
        '"texto_fuente": "cartel que dice \'Calle Falsa 123\'", "confianza_extraccion": 0.6, "razon": "texto legible en la imagen"}]'
    )

    async def fake_ner_create(**kwargs):
        return _fake_response(payload)

    monkeypatch.setattr(ner.client.chat.completions, "create", fake_ner_create)
    ner_result = await ner.propose_entities(description, archivo_id)
    ner.save_proposals(cases_dir, "caso-1", ner_result.proposals)

    pending = ner.read_proposals(cases_dir, "caso-1", status="pendiente")
    assert len(pending) == 1
    assert pending[0].artefacto_origen == archivo_id
