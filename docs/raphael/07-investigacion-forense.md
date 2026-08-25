# 07 · Investigación y análisis forense (`app/investigation/`)

Tercer dominio de grafo de Raphael (aparte de código y conocimiento): análisis de enlaces y evidencia
digital para casos forenses. Spec 2026-08-12. **Alcance no negociable** (impuesto en el prompt del skill
`investigation`): solo analiza material que Damian **ya tiene** legítimamente — nunca scraping, nunca
agregadores de datos personales, nunca deanonimización/geolocalización de personas, nunca sale a buscar
nada por su cuenta. El rol del LLM está acotado a 4 cosas: extracción de entidades, normalización de
variantes, hipótesis sobre subgrafos ya confirmados, y borradores de informe — **nunca concluye,
puntúa culpabilidad ni infiere identidades reales**.

## Principios estructurales

- **Un caso = un repo git propio** (versiona grafo/log/metadata, nunca los binarios).
- **Artifact store único compartido**, indexado por sha256, de solo lectura, **nunca versionado**.
- **Log append-only firmado con Ed25519** (clave protegida con DPAPI), con hash-chaining.
- **Todo lo que el modelo propone pasa por confirmación humana** antes de tocar el grafo.

## Modelo de datos (`models.py`)

- **`NodeType`** (enum): Persona, Cuenta, Dispositivo, Host, Archivo, Transaccion, Evento, Organizacion.
- **`EdgeType`** (enum): incluye `mismo_que`, `aparece_en`, etc.
- **`DerivadaPor`** (enum): marca el origen de un dato (humano/modelo).
- **`Node`** / **`Edge`** — con `confianza` (0–1, `_validate_confianza`), `campos` validados por tipo
  (`_validate_campos`), `retract(reason)` (retracción no destructiva), `to_dict`/`from_dict`. IDs
  determinísticos por clave natural (`deterministic_node_id`) o aleatorios (`_random_node_id`).
- **Factories:** `make_persona`, `make_cuenta`, `make_dispositivo`, `make_host`, `make_archivo`,
  `make_transaccion`, `make_evento`, `make_organizacion`, `make_edge`.

## Almacenamiento y trazabilidad

- **`keys.py`** — `ensure_keypair(keys_dir)` (Ed25519, DPAPI), `load_private_key`/`load_public_key`,
  `sign(private_key, data)`, `verify(public_key, data, sig)`.
- **`log.py`** — log append-only con integridad: `append_entry(...)` encadena por hash
  (`_entry_hash`/`_canonical_bytes`) y firma; `verify_chain(...)` valida toda la cadena
  (`VerificationResult`); `read_entries`, `_last_entry`. `CorruptedLogError` si se detecta manipulación.
- **`artifact_store.py`** — `store_artifact(store_dir, data, name, ingested_by)` guarda por sha256
  (`_object_path`/`_record_path`, `ArtifactRecord`), `read_record`, `read_artifact_bytes`,
  `set_ingestion_marker`.
- **`case_store.py`** — CRUD del grafo con git y locking por caso (`_lock_for`, `batch(...)` context
  manager que commitea al final). `create_case`, `add_node`/`add_edge`, `retract_node`/`retract_edge`,
  `read_nodes`/`read_edges`, `rebuild_from_log` (reconstruye el grafo desde el log firmado). JSONL con
  `_append_jsonl`/`_read_jsonl`/`_rewrite_jsonl`.

## Ingesta

- **`csv_parser.py`** — `ingest_csv(...)` crea un nodo por fila según un `column_mapping` confirmado
  (`make_node_from_row`, `_coerce_value`). `_decode_csv_bytes` maneja encodings.
- **`column_mapping.py`** — `propose_mapping(node_type, columns, sample_rows)` **el modelo solo propone**
  a qué campo del schema va cada columna (`MappingProposal`); `save_mapping`/`load_saved_mapping` reusan
  un mapeo confirmado para la misma estructura de columnas (`source_signature`).
- **`chat_parser.py`** — `ingest_whatsapp_export` / `ingest_telegram_export` (determinísticos, sin modelo)
  → un nodo Evento por mensaje. `_parse_whatsapp_messages`/`_parse_telegram_messages`,
  `_resolve_sender_node`. Telegram deduplica bien (trae id de conversación); WhatsApp puede duplicar en
  re-exports.
- **`server_log_parser.py`** — `ingest_server_log(...)` autodetecta access log vs auth log
  (`detect_format`/`_score_format`, `_parse_access_log`/`_parse_auth_log`).
- **`exif_parser.py`** — `ingest_image(...)` guarda el artefacto y lee EXIF real
  (`extract_exif_metadata`, GPS vía `_extract_gps`/`_dms_to_decimal`, fecha vía `_exif_datetime_to_iso`).
  `describe_image_content(image_bytes)` le pide al modelo de visión una descripción **objetiva** (nunca
  identidad).
- **`doc_parser.py`** — `ingest_document(...)` detecta el formato por la firma real de los bytes
  (`detect_document_format`) y extrae texto (`extract_pdf_text` con pypdf, `extract_docx_text` con
  python-docx).

## NER (extracción de entidades) — `ner.py`

`propose_entities(texto, artefacto_origen)` le pide al modelo que **proponga** entidades
(`EntityProposal`/`NerResult`, tipos vía `_entity_types_prompt_block`, campos coercionados/limpiados con
`_coerce_campos`/`_strip_empty_values`, parseo `_parse_candidates`). **Nunca escribe al grafo.**
`save_proposals`/`read_proposals` (persistidas en el caso), `confirm_proposal(...)` (crea el nodo real
con su arista de derivación), `reject_proposal(...)`.

## Fusión de identidades — `fusion.py`

`propose_fusion(node_a, node_b)` compara dos nodos del **mismo tipo** y evalúa si son la misma entidad
real (`FusionProposal` con confianza + motivo, `_parse_proposal_response`). `confirm_fusion(...)` crea
una arista `mismo_que` real **pero los dos nodos originales siguen existiendo intactos** (la fusión es
retractable). `reject_fusion(...)`, `save_proposal`/`read_proposals`.

## Análisis del grafo

- **`graph_metrics.py`** — `build_graph(nodes, edges)` (networkx), `compute_centrality` (intermediación:
  candidatos a pivote), `compute_confidence`, `detect_communities` (Louvain, seed fijo).
- **`timeline.py`** — `normalize_timestamp(raw)` (python-dateutil, formatos variados),
  `build_timeline(nodes, edges)` (`TimelineEntry`), `timeline_for_entity(...)`,
  `detect_contradictions(...)` (`Contradiction`: ej. dos ubicaciones incompatibles en el tiempo).

## Export de informe — `report_export.py`

`export_report(cases_dir, keys_dir, case_id)` genera Markdown **y** PDF reales:
`build_report_data(...)` (`ReportData`: `EntityRow`, `ArtifactRow` con hash, `ModelGeneratedEdgeRow`),
`render_graph_png(...)` (matplotlib + spring_layout de networkx), `render_markdown(...)`,
`render_pdf(...)` (fpdf2). Una sección aparte marca todo lo generado por el modelo, con referencia al
artefacto que lo originó, nunca mezclado con dato verificado.

## Tools (`tools/investigation.py`) — 18 tools

`investigation_create_case`, `investigation_propose_column_mapping`, `investigation_ingest_csv`,
`investigation_propose_entities`, `investigation_list_pending_proposals`, `investigation_confirm_proposal`,
`investigation_reject_proposal`, `investigation_ingest_whatsapp_export`, `investigation_ingest_telegram_export`,
`investigation_ingest_server_log`, `investigation_ingest_image`, `investigation_describe_image`,
`investigation_ingest_document`, `investigation_propose_fusion`, `investigation_list_pending_fusions`,
`investigation_confirm_fusion`, `investigation_reject_fusion`, `investigation_export_report`.

Router HTTP asociado: `/api/investigation/*` (ver [11](11-servidor-fastapi.md)). Directorios:
`INVESTIGATION_CASES_DIR`, `INVESTIGATION_ARTIFACT_STORE_DIR`, `INVESTIGATION_KEYS_DIR` (ver [15](15-configuracion.md)).
