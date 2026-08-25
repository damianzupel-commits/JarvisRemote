"""Tests del pipeline de ingesta de YouTube al vault
(app/ingestion/youtube_playlist.py).

Todo con datos SIMULADOS: se mockean las tres únicas piezas que tocan la red
real de YouTube o el LLM -- `fetch_playlist_entries` (yt-dlp),
`fetch_transcript` (youtube-transcript-api) y `_call_llm` (el LLM de chat).
El resto (detección de nuevos, formato de nota, idempotencia, actualización
del índice) corre contra un vault real en un tmp_path, como
test_obsidian_vault.py / test_research_tool.py -- así se verifica el contenido
producido de verdad, no solo que se hayan llamado los mocks.

⚠️ Estos tests NO prueban el pipeline contra YouTube real (el entorno lo
bloquea); solo la lógica del repo alrededor. Ver el docstring del módulo.
"""

from __future__ import annotations

import json

import pytest

from app.obsidian import embeddings, vault
from app.ingestion import youtube_playlist as yt


@pytest.fixture(autouse=True)
def _tmp_vault(tmp_path, monkeypatch):
    """Vault e índice de embeddings aislados en tmp_path (los embeddings ya
    quedan neutralizados por el fixture _no_real_embeddings de conftest)."""
    monkeypatch.setattr(vault.settings, "obsidian_vault_path", str(tmp_path / "vault"))
    monkeypatch.setattr(embeddings.settings, "obsidian_embeddings_path", str(tmp_path / "embeddings.json"))
    return tmp_path / "vault"


def _seed_index() -> None:
    """Crea la nota índice de la playlist con un video ya listado, replicando
    el estado real del vault (índice + 1 nota de video previa)."""
    index_body = (
        'Playlist de YouTube de Damian, "Info para Jarvis" '
        "(https://www.youtube.com/playlist?list=PLVjx_ae3DGSo), procesada con NotebookLM. 1 videos.\n\n"
        "- [[Nota vieja de prueba]] — Video Viejo (Canal Viejo, categoría: pentesting)"
    )
    vault.save_note(
        title=yt.INDEX_NOTE_TITLE,
        content=index_body,
        author="jarvis",
        tags=["indice", "playlist", "info-para-jarvis"],
        category="",
        note_id=yt.INDEX_NOTE_ID,
    )


def _seed_existing_video_note(video_id: str) -> None:
    """Crea una nota de video existente con el video_id embebido en ## Fuente,
    igual que las 8 notas reales -- así el pipeline la detecta como ya
    procesada."""
    body = (
        "Resumen viejo.\n\n## Fuente\n"
        f"- Video: https://www.youtube.com/watch?v={video_id}\n"
        "- Canal: Canal Viejo\n- Generado con: NotebookLM (Google)\n"
    )
    vault.save_note(
        title="Nota vieja de prueba",
        content=body,
        author="jarvis",
        tags=["info-para-jarvis", "video", "pentesting"],
        category="pentesting",
    )


def _fake_llm_response(title="Título curado", category="pentesting"):
    payload = {
        "title": title,
        "category": category,
        "summary": "Una oración. Dos oraciones. Tres oraciones. Cuatro oraciones.",
        "key_topics": ["Tema A", "Tema B", "Tema C", "Tema D"],
    }
    return json.dumps(payload)


def _fake_relevance_response(verdict="útil", score=5, reason="Trata directamente de pentesting."):
    return json.dumps({"verdict": verdict, "score": score, "reason": reason})


def _is_relevance_prompt(messages) -> bool:
    """El pipeline llama a _call_llm dos veces por video (relevancia y resumen).
    El prompt de relevancia pide la clave "verdict"; el de resumen no. Con eso
    el mock devuelve la respuesta correcta a cada llamada."""
    system = messages[0]["content"] if messages else ""
    return '"verdict"' in system


def _patch_externals(monkeypatch, entries, transcripts, llm_response=None, relevance_response=None):
    """Mockea las tres fronteras externas. `transcripts` es {video_id: texto|None}.
    `llm_response` fija la salida del RESUMEN; `relevance_response` la del
    discernimiento de relevancia (default: útil/5)."""
    monkeypatch.setattr(yt, "fetch_playlist_entries", lambda url: entries)
    monkeypatch.setattr(yt, "fetch_transcript", lambda vid: transcripts.get(vid))

    async def _fake_call_llm(messages):
        if _is_relevance_prompt(messages):
            return relevance_response if relevance_response is not None else _fake_relevance_response()
        return llm_response if llm_response is not None else _fake_llm_response()

    monkeypatch.setattr(yt, "_call_llm", _fake_call_llm)


# ---------------------------------------------------------------------------
# 1. Detección de videos nuevos vs ya procesados.
# ---------------------------------------------------------------------------


def test_existing_video_ids_parsea_del_cuerpo(monkeypatch):
    _seed_existing_video_note("hu4QKjhXJLk")
    ids = yt.existing_video_ids()
    assert "hu4QKjhXJLk" in ids


def test_select_new_videos_excluye_presentes_y_deduplica():
    entries = [
        yt.VideoEntry("aaaaaaaaaaa", "Nuevo A"),
        yt.VideoEntry("bbbbbbbbbbb", "Ya presente"),
        yt.VideoEntry("aaaaaaaaaaa", "Nuevo A duplicado en playlist"),
    ]
    new = yt.select_new_videos(entries, already={"bbbbbbbbbbb"})
    assert [e.video_id for e in new] == ["aaaaaaaaaaa"]


@pytest.mark.anyio
async def test_ingest_crea_solo_los_nuevos(monkeypatch):
    _seed_index()
    _seed_existing_video_note("bbbbbbbbbbb")
    entries = [
        yt.VideoEntry("bbbbbbbbbbb", "Video ya procesado", channel="Canal Viejo"),
        yt.VideoEntry("ccccccccccc", "Video nuevo", channel="Canal Nuevo", duration="10:00"),
    ]
    _patch_externals(monkeypatch, entries, {"ccccccccccc": "transcripción real del video nuevo"})

    result = await yt.ingest_playlist("https://youtube.com/playlist?list=X")

    assert result.total_in_playlist == 2
    assert result.already_present == ["bbbbbbbbbbb"]
    assert len(result.created) == 1
    assert result.created[0]["video_id"] == "ccccccccccc"


# ---------------------------------------------------------------------------
# 2. Generación de la nota con el formato correcto.
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_nota_generada_tiene_formato_exacto(monkeypatch):
    _seed_index()
    entries = [yt.VideoEntry("ccccccccccc", "Título original YT", channel="Alvaro Chirou", duration="29:15")]
    _patch_externals(
        monkeypatch,
        entries,
        {"ccccccccccc": "una transcripción cualquiera"},
        llm_response=_fake_llm_response(title="Resumen curado del video", category="pentesting"),
    )

    result = await yt.ingest_playlist("url")
    note = vault.read_note(result.created[0]["note_id"])

    # Frontmatter
    assert note.author == "jarvis"
    assert note.category == "pentesting"
    assert note.tags == ["info-para-jarvis", "video", "pentesting"]
    assert note.title == "Resumen curado del video"

    # Secciones exactas
    assert "## Fuente" in note.content
    assert "## Resumen" in note.content
    assert "## Temas clave" in note.content
    assert "## Notas relacionadas" in note.content

    # Fuente con el marcador de generación automática y la URL del video
    assert "- Video: https://www.youtube.com/watch?v=ccccccccccc" in note.content
    assert "- Canal: Alvaro Chirou" in note.content
    assert "- Duración: 29:15" in note.content
    assert "- Generado con: resumen automático" in note.content

    # Wikilinks al índice de categoría y al índice de la playlist
    assert "- [[Índice: pentesting]]" in note.content
    assert f"- [[{yt.INDEX_NOTE_TITLE}]]" in note.content

    # Temas clave como bullets
    assert "- Tema A" in note.content


# ---------------------------------------------------------------------------
# 3. Idempotencia: correr dos veces no duplica.
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_idempotencia_no_duplica(monkeypatch):
    _seed_index()
    entries = [yt.VideoEntry("ccccccccccc", "Video nuevo", channel="Canal", duration="5:00")]
    _patch_externals(monkeypatch, entries, {"ccccccccccc": "transcripción"})

    first = await yt.ingest_playlist("url")
    assert len(first.created) == 1

    # Segunda corrida idéntica: el video ya tiene nota -> nada nuevo.
    second = await yt.ingest_playlist("url")
    assert len(second.created) == 0
    assert "ccccccccccc" in second.already_present

    # Solo una nota de video para ese ID (además del índice).
    video_notes = [n for n in vault.list_notes(author="jarvis") if "video" in n.tags]
    assert len(video_notes) == 1


# ---------------------------------------------------------------------------
# 4. Actualización del índice.
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_indice_agrega_wikilink_y_sube_conteo(monkeypatch):
    _seed_index()  # arranca con "1 videos." y un bullet
    entries = [yt.VideoEntry("ccccccccccc", "Video original", channel="Canal Nuevo", duration="8:00")]
    _patch_externals(
        monkeypatch,
        entries,
        {"ccccccccccc": "transcripción"},
        llm_response=_fake_llm_response(title="Nota nueva de video", category="osint"),
    )

    await yt.ingest_playlist("url")
    index = vault.read_note(yt.INDEX_NOTE_ID)

    assert "- [[Nota nueva de video]]" in index.content
    assert "Video original" in index.content
    assert "categoría: osint" in index.content
    # El conteo se recalculó de 1 a 2 bullets de video.
    assert "2 videos." in index.content
    assert "1 videos." not in index.content


@pytest.mark.anyio
async def test_indice_no_se_duplica_en_segunda_corrida(monkeypatch):
    _seed_index()
    entries = [yt.VideoEntry("ccccccccccc", "Video original", channel="Canal", duration="8:00")]
    _patch_externals(monkeypatch, entries, {"ccccccccccc": "transcripción"})

    await yt.ingest_playlist("url")
    await yt.ingest_playlist("url")

    index = vault.read_note(yt.INDEX_NOTE_ID)
    # El wikilink del video nuevo aparece una sola vez.
    assert index.content.count("[[Título curado]]") == 1


# ---------------------------------------------------------------------------
# 5. Video sin transcripción disponible.
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_video_sin_transcripcion_se_saltea(monkeypatch):
    _seed_index()
    entries = [
        yt.VideoEntry("ccccccccccc", "Con transcripción", channel="C1", duration="3:00"),
        yt.VideoEntry("ddddddddddd", "Sin transcripción", channel="C2", duration="4:00"),
    ]
    _patch_externals(
        monkeypatch,
        entries,
        {"ccccccccccc": "hay texto", "ddddddddddd": None},
    )

    result = await yt.ingest_playlist("url")

    assert len(result.created) == 1
    assert result.created[0]["video_id"] == "ccccccccccc"
    assert len(result.skipped_no_transcript) == 1
    assert result.skipped_no_transcript[0]["video_id"] == "ddddddddddd"

    # No se creó ninguna nota para el video sin transcripción.
    titles = [n.title for n in vault.list_notes(author="jarvis")]
    assert "Sin transcripción" not in titles


# ---------------------------------------------------------------------------
# 5b. fetch_transcript contra la API real de youtube-transcript-api 1.2.4.
#     Se mockea SOLO YouTubeTranscriptApi (la frontera de red); se ejercita la
#     lógica real de fetch_transcript (que antes usaba el classmethod viejo
#     get_transcript() y rompía contra 1.2.4).
# ---------------------------------------------------------------------------


class _FakeSnippet:
    """Imita FetchedTranscriptSnippet de 1.2.4: objeto con atributo .text
    (NO un dict como en la API vieja)."""

    def __init__(self, text):
        self.text = text


class _FakeFetched:
    """Imita FetchedTranscript de 1.2.4: expone .snippets (lista de snippets)."""

    def __init__(self, snippets):
        self.snippets = snippets


def test_fetch_transcript_usa_nueva_api_de_instancia(monkeypatch):
    """La versión 1.2.4 exige `YouTubeTranscriptApi().fetch(video_id,
    languages=[...])` -> FetchedTranscript con .snippets[].text. Verificamos que
    fetch_transcript llame así y una el texto de los snippets (ignorando vacíos)."""
    import youtube_transcript_api as yta_mod

    llamada = {}

    class _FakeApi:
        def fetch(self, video_id, languages=None):
            llamada["video_id"] = video_id
            llamada["languages"] = languages
            return _FakeFetched([_FakeSnippet("Hola"), _FakeSnippet("mundo"), _FakeSnippet("   ")])

    monkeypatch.setattr(yta_mod, "YouTubeTranscriptApi", _FakeApi)

    text = yt.fetch_transcript("qImiSKSR9_g")

    assert text == "Hola mundo"  # snippets unidos por espacio, el vacío descartado
    assert llamada["video_id"] == "qImiSKSR9_g"
    # Prefiere español, cae a inglés (lista de preferencia del módulo).
    assert llamada["languages"] == yt._TRANSCRIPT_LANGS


def test_fetch_transcript_sin_subtitulos_devuelve_none(monkeypatch):
    """TranscriptsDisabled/NoTranscriptFound = el video no tiene subtítulos ->
    None (se saltea con gracia), NO se propaga como error técnico."""
    import youtube_transcript_api as yta_mod

    class _FakeApi:
        def fetch(self, video_id, languages=None):
            raise yta_mod.TranscriptsDisabled(video_id)

    monkeypatch.setattr(yta_mod, "YouTubeTranscriptApi", _FakeApi)

    assert yt.fetch_transcript("vvvvvvvvvvv") is None


def test_fetch_transcript_error_tecnico_propaga(monkeypatch):
    """Un error que NO es falta de subtítulos (ej. IpBlocked) se PROPAGA, para
    que el pipeline lo reporte con su motivo en vez de disfrazarlo de 'sin
    transcripción'."""
    import youtube_transcript_api as yta_mod

    class _FakeApi:
        def fetch(self, video_id, languages=None):
            raise yta_mod.IpBlocked(video_id)

    monkeypatch.setattr(yta_mod, "YouTubeTranscriptApi", _FakeApi)

    with pytest.raises(yta_mod.IpBlocked):
        yt.fetch_transcript("wwwwwwwwwww")


@pytest.mark.anyio
async def test_error_tecnico_de_transcripcion_se_reporta_con_motivo(monkeypatch):
    """Un fallo TÉCNICO al bajar la transcripción de un video NO se debe saltear
    en silencio como 'sin subtítulos': se reporta en transcript_errors con su
    motivo real, sin tumbar la corrida ni impedir procesar los demás videos."""
    _seed_index()
    entries = [
        yt.VideoEntry("ccccccccccc", "Con transcripción", channel="C1", duration="3:00"),
        yt.VideoEntry("ddddddddddd", "Falla técnica", channel="C2", duration="4:00"),
    ]

    def _fetch(vid):
        if vid == "ddddddddddd":
            # Simula un error técnico real (bloqueo de IP), no falta de subtítulos.
            raise RuntimeError("IpBlocked: la IP fue bloqueada por YouTube")
        return "hay texto de transcripción"

    monkeypatch.setattr(yt, "fetch_playlist_entries", lambda url: entries)
    monkeypatch.setattr(yt, "fetch_transcript", _fetch)

    async def _fake_call_llm(messages):
        if _is_relevance_prompt(messages):
            return _fake_relevance_response()
        return _fake_llm_response(title="Nota buena", category="pentesting")

    monkeypatch.setattr(yt, "_call_llm", _fake_call_llm)

    result = await yt.ingest_playlist("url")

    # El video sano se procesó normalmente.
    assert len(result.created) == 1
    assert result.created[0]["video_id"] == "ccccccccccc"

    # El fallo técnico se reportó con su MOTIVO, diferenciado de "sin subtítulos".
    assert len(result.transcript_errors) == 1
    err = result.transcript_errors[0]
    assert err["video_id"] == "ddddddddddd"
    assert "IpBlocked" in err["error"]  # el motivo real quedó registrado
    assert "RuntimeError" in err["error"]  # y el tipo de excepción también

    # NO se ocultó como falta de subtítulos ni se creó una nota para él.
    assert len(result.skipped_no_transcript) == 0
    titles = [n.title for n in vault.list_notes(author="jarvis")]
    assert "Falla técnica" not in titles

    # Y quedó expuesto en el dict serializable de la tool.
    assert result.to_dict()["transcript_errors_count"] == 1


# ---------------------------------------------------------------------------
# Extra: parseo robusto del JSON del LLM (envuelto en fence / con ruido).
# ---------------------------------------------------------------------------


def test_parse_summary_tolera_fence_markdown():
    entry = yt.VideoEntry("ccccccccccc", "orig")
    raw = "```json\n" + _fake_llm_response(title="X", category="Y") + "\n```"
    parsed = yt._parse_summary(raw, entry)
    assert parsed["title"] == "X"
    assert parsed["category"] == "y"  # normalizado a minúsculas


def test_parse_summary_cae_a_defaults_si_no_es_json():
    entry = yt.VideoEntry("ccccccccccc", "Título original")
    parsed = yt._parse_summary("esto no es json", entry)
    assert parsed["title"] == "Título original"  # cae al título del video
    assert parsed["category"] == "general"


# ---------------------------------------------------------------------------
# 6. Discernimiento de relevancia (agregado 2026-08-18).
# ---------------------------------------------------------------------------


def _read_frontmatter(note_id: str) -> dict:
    """Lee el frontmatter crudo del .md de la nota (VaultNote no expone las
    properties extra como `relevancia`)."""
    import frontmatter

    path = vault._note_path(note_id)
    return frontmatter.loads(path.read_text(encoding="utf-8")).metadata


def test_parse_relevance_util():
    entry = yt.VideoEntry("ccccccccccc", "orig")
    parsed = yt._parse_relevance(_fake_relevance_response("útil", 5, "Sobre hacking."), entry)
    assert parsed["verdict"] == "útil"
    assert parsed["score"] == 5
    assert parsed["reason"] == "Sobre hacking."
    assert parsed["is_low"] is False


def test_parse_relevance_normaliza_variantes_y_recorta_score():
    entry = yt.VideoEntry("ccccccccccc", "orig")
    # "no util" sin tilde + score fuera de rango (8 -> 5).
    parsed = yt._parse_relevance(json.dumps({"verdict": "no util", "score": 8, "reason": "x"}), entry)
    assert parsed["verdict"] == "no útil"
    assert parsed["score"] == 5
    # is_low por veredicto "no útil" aunque el score sea alto.
    assert parsed["is_low"] is True


def test_parse_relevance_cae_a_defaults_si_no_es_json():
    entry = yt.VideoEntry("ccccccccccc", "orig")
    parsed = yt._parse_relevance("esto no es json", entry)
    assert parsed["verdict"] == "dudoso"  # derivado del score neutro 3
    assert parsed["score"] == 3
    assert parsed["reason"] == "(sin justificación generada)"


def test_parse_relevance_score_bajo_marca_low():
    entry = yt.VideoEntry("ccccccccccc", "orig")
    parsed = yt._parse_relevance(_fake_relevance_response("dudoso", 2, "Poco que ver."), entry)
    assert parsed["is_low"] is True  # score <= 2


@pytest.mark.anyio
async def test_nota_incluye_campos_de_relevancia(monkeypatch):
    _seed_index()
    entries = [yt.VideoEntry("ccccccccccc", "Video YT", channel="Canal", duration="10:00")]
    _patch_externals(
        monkeypatch,
        entries,
        {"ccccccccccc": "una transcripción"},
        llm_response=_fake_llm_response(title="Nota útil", category="hacking"),
        relevance_response=_fake_relevance_response("útil", 5, "Trata de hacking ofensivo."),
    )

    result = await yt.ingest_playlist("url")
    note = vault.read_note(result.created[0]["note_id"])
    fm = _read_frontmatter(result.created[0]["note_id"])

    # Frontmatter con las properties de relevancia.
    assert fm["relevancia"] == "útil"
    assert fm["relevancia_score"] == 5

    # Sección ## Relevancia con veredicto, puntaje y razón.
    assert "## Relevancia" in note.content
    assert "- Veredicto: útil" in note.content
    assert "- Puntaje: 5/5" in note.content
    assert "- Razón: Trata de hacking ofensivo." in note.content

    # Una nota útil NO lleva el tag ni la advertencia de baja relevancia.
    assert "baja-relevancia" not in note.tags
    assert "baja relevancia" not in note.content

    # El resultado expone veredicto y puntaje por video creado.
    assert result.created[0]["relevancia"] == "útil"
    assert result.created[0]["relevancia_score"] == 5


@pytest.mark.anyio
async def test_no_util_se_marca_pero_se_crea_igual(monkeypatch):
    """El requisito central de Damian: aunque sea "no útil", la nota SE CREA;
    la relevancia es etiqueta, no filtro."""
    _seed_index()
    entries = [yt.VideoEntry("ccccccccccc", "Video off-topic", channel="Canal", duration="10:00")]
    _patch_externals(
        monkeypatch,
        entries,
        {"ccccccccccc": "una transcripción"},
        llm_response=_fake_llm_response(title="Nota off-topic", category="varios"),
        relevance_response=_fake_relevance_response("no útil", 1, "No tiene que ver con los temas."),
    )

    result = await yt.ingest_playlist("url")

    # SE CREÓ igual (nunca se saltea por baja relevancia sin --min-relevance).
    assert len(result.created) == 1
    assert len(result.skipped_low_relevance) == 0

    note = vault.read_note(result.created[0]["note_id"])
    fm = _read_frontmatter(result.created[0]["note_id"])

    assert fm["relevancia"] == "no útil"
    assert fm["relevancia_score"] == 1
    # Tag de baja relevancia presente.
    assert "baja-relevancia" in note.tags
    # Advertencia visible al inicio de la sección.
    assert "⚠️ Marcada como baja relevancia — guardada igual por curaduría de Damian." in note.content
    assert "- Veredicto: no útil" in note.content


@pytest.mark.anyio
async def test_default_no_filtra_nada_por_relevancia(monkeypatch):
    """Sin --min-relevance, incluso un video "no útil"/score 1 se guarda."""
    _seed_index()
    entries = [
        yt.VideoEntry("ccccccccccc", "Útil", channel="C1", duration="3:00"),
        yt.VideoEntry("ddddddddddd", "No útil", channel="C2", duration="4:00"),
    ]

    def _relevance_por_video(messages):
        # El user prompt lleva el título original -> discriminamos por ahí.
        user = messages[1]["content"]
        if "No útil" in user:
            return _fake_relevance_response("no útil", 1, "Off-topic.")
        return _fake_relevance_response("útil", 5, "On-topic.")

    monkeypatch.setattr(yt, "fetch_playlist_entries", lambda url: entries)
    monkeypatch.setattr(yt, "fetch_transcript", lambda vid: "transcripción")

    async def _fake_call_llm(messages):
        if _is_relevance_prompt(messages):
            return _relevance_por_video(messages)
        return _fake_llm_response(title=f"Nota {messages[1]['content'][:8]}", category="varios")

    monkeypatch.setattr(yt, "_call_llm", _fake_call_llm)

    result = await yt.ingest_playlist("url")  # default: min_relevance=None

    # Ambos videos se procesaron; nada saltado por relevancia.
    assert len(result.created) == 2
    assert len(result.skipped_low_relevance) == 0
    breakdown = result.relevance_breakdown()
    assert breakdown["útil"] == 1
    assert breakdown["no útil"] == 1


@pytest.mark.anyio
async def test_min_relevance_explicito_saltea_bajos(monkeypatch):
    """SOLO con --min-relevance explícito se saltea: score < N no crea nota,
    pero se reporta en skipped_low_relevance."""
    _seed_index()
    entries = [
        yt.VideoEntry("ccccccccccc", "Útil", channel="C1", duration="3:00"),
        yt.VideoEntry("ddddddddddd", "No útil", channel="C2", duration="4:00"),
    ]

    monkeypatch.setattr(yt, "fetch_playlist_entries", lambda url: entries)
    monkeypatch.setattr(yt, "fetch_transcript", lambda vid: "transcripción")

    async def _fake_call_llm(messages):
        user = messages[1]["content"]
        if _is_relevance_prompt(messages):
            if "No útil" in user:
                return _fake_relevance_response("no útil", 1, "Off-topic.")
            return _fake_relevance_response("útil", 5, "On-topic.")
        return _fake_llm_response(title=f"Nota {user[:8]}", category="varios")

    monkeypatch.setattr(yt, "_call_llm", _fake_call_llm)

    result = await yt.ingest_playlist("url", min_relevance=3)

    # Solo el útil (score 5) se creó; el score 1 se saltó por el filtro explícito.
    assert len(result.created) == 1
    assert result.created[0]["relevancia"] == "útil"
    assert len(result.skipped_low_relevance) == 1
    assert result.skipped_low_relevance[0]["video_id"] == "ddddddddddd"
    assert result.skipped_low_relevance[0]["relevancia_score"] == 1


def test_ingest_result_to_dict_incluye_relevancia():
    r = yt.IngestResult(playlist_url="u")
    r.created.append({"video_id": "x", "note_id": "jarvis/x", "title": "T", "relevancia": "útil", "relevancia_score": 4})
    d = r.to_dict()
    assert d["relevance_breakdown"]["útil"] == 1
    assert d["skipped_low_relevance_count"] == 0
    assert d["transcript_errors_count"] == 0
