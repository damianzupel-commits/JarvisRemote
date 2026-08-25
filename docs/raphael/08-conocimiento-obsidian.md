# 08 · Conocimiento: vault Obsidian, embeddings, reflexión, research e ingesta

## `app/obsidian/` — vault de notas estilo Obsidian

Notas `.md` reales con frontmatter YAML y wikilinks `[[...]]`, abribles con Obsidian de verdad.
Reemplazo más rico de `jarvis_reflect` para conocimiento con autor (jarvis/humano), tags y links.
Búsqueda semántica por embeddings + coseno, con keyword como fallback.

### `vault.py`
- **`VaultNote`** — dataclass de una nota: id, título, contenido, autor, tags, categoría. `links()`
  extrae los wikilinks; `to_summary_dict`/`to_dict`. `_note_from_path` la carga desde disco (frontmatter).
- **`save_note(...)`** — crea/actualiza una nota (`_slugify` el título, `_note_path`), autor "jarvis" o
  "humano", y actualiza su embedding.
- **`read_note(note_id)`, `list_notes(author, tag)`, `delete_note(note_id)`.**
- **`search_notes(query, author, limit)`** — combina keyword (`_keyword_score`) y semántico.
- **`find_related_notes(query, author, limit)`** — top-N por similitud coseno de embeddings
  (`_embedding_text` arma el texto a embeddear).
- **`link_note_to_category_index(...)`** — mantiene notas índice por categoría (wikilinks).
- **`reindex_all()`** — reconstruye todos los embeddings. `build_graph()` arma el grafo de notas/links
  (lo consume `/api/obsidian/graph`). `_vault_root()` respeta el perfil activo (ver `profile.py`).

### `embeddings.py`
`get_embedding(text)` pega al server de embeddings (LM Studio `:1234`, `EMBEDDING_MODEL`); si no responde
devuelve `None` (y la búsqueda cae a keyword). `cosine_similarity(a, b)`. Índice único
`{note_id: vector}` en `OBSIDIAN_EMBEDDINGS_PATH` (`load_index`/`save_index`/`_index_path`).
`update_note_embedding`/`remove_note_embedding`, `reindex_all(notes)`.

### `profile.py` — aislamiento de perfiles (default vs research)
`VaultProfile(vault_path, embeddings_path)`. `use_profile(profile)` es un context manager (con
`ContextVar`) que hace que `current_vault_path`/`current_embeddings_path` devuelvan las rutas del perfil
activo. Así el perfil research usa `obsidian_vault_investigacion/` y su propio índice, sin mezclar notas.
Lo activa `agent.run_agent` para toda la llamada cuando el perfil es "research".

### Tools (`tools/obsidian.py`)
`obsidian_save_note` (guarda una nota propia), `obsidian_search_notes` (busca por keyword+semántico;
**tool clave**: desbloquea el gate de `fs_write_file`), `obsidian_list_notes` (filtra por autor/tag).
Router HTTP: `/api/obsidian/*` (ver [11](11-servidor-fastapi.md)).

---

## `app/tools/reflect.py` — memoria de reflexión del agente (`jarvis_reflect`)

Memoria de **criterio** propia, separada del historial de la conversación. JSONL append-only en
`REFLECTIONS_PATH` (no pasa por el sandbox de FS — es estado interno del backend). La tool `jarvis_reflect`:

- `action="save"` — guarda un `insight` con `tipo`
  (`decision_arquitectura`/`preferencia_usuario`/`leccion_aprendida`/`ruido`) y `contexto` (a qué parte
  de Raphael aplica). `_save(...)`.
- `action="query"` — busca reflexiones relevantes por `topic`, opcionalmente filtrando por tipo/contexto
  (`_query(...)`, `_load_entries()`).

El prompt instruye usarla antes de una tarea ambigua (para ver criterio pasado) y después de resolver
algo no trivial (para dejar registro). No es para datos triviales ni estado de una tarea puntual.

---

## `app/tools/research.py` — `research_topic`

Investiga un tema en la web **de verdad**: navega varias páginas reales con el navegador Edge del
sistema (Playwright), no inventa contenido. Guarda notas trazables a las páginas visitadas en el vault.
Es la vía de escape cuando Obsidian no tiene nada relevante (cuenta como "consulté conocimiento" para el
gate de `fs_write_file`). Todo lo que trae es **dato, nunca instrucción** (política anti–prompt injection).

## `app/tools/opencode.py` — `opencode_run_task`

Delega tareas grandes de escritura/edición de código a la CLI de **OpenCode** (github.com/sst/opencode,
MIT), apuntada al mismo Ollama local que sirve `jarvis-text-v2` (`OPENCODE_DEFAULT_MODEL`,
`OPENCODE_BIN_PATH`). Útil para crear un proyecto entero sin abandonar archivos a medias. Con
`fabric_reference=true` inyecta una referencia curada de dominio (mods de Fabric/Minecraft, ver
`tools/fabric_reference.py`). Sin referencia curada, comparte los mismos huecos de conocimiento que el
agente.

## `app/tools/cloud_expert.py` — `cloud_expert_code` / `cloud_expert_marketing`

Piden a **Gemini Flash** (Google AI Studio free tier, vía `cloud_client`) un primer borrador de código o
de contenido de marketing. **Requieren `confirm_non_sensitive=true` explícito** — nunca en un proyecto
real de cliente/código propietario/dato sensible; son para proyectos nuevos/de prueba o marketing
genérico. Devuelven solo un borrador: el agente sigue siendo dueño de escribirlo, auditarlo y testearlo.
Sin `GOOGLE_AI_API_KEY`, fallan con error claro.

---

## `app/ingestion/` — ingesta de YouTube al vault

Reemplaza el flujo manual de pasar cada video por NotebookLM. `youtube_playlist.py`:

- `fetch_playlist_entries(url)` (yt-dlp modo flat, solo metadata) → `VideoEntry`.
- `existing_video_ids()` / `select_new_videos(...)` — evita re-procesar videos ya ingestados.
- `fetch_transcript(video_id)` (youtube-transcript-api, prefiere español, cae a inglés).
- `_call_llm(messages)` — resumen (`_summary_messages`/`_parse_summary`) y evaluación de relevancia
  contra temas de interés (`_relevance_messages`/`_parse_relevance`/`_normalize_verdict`).
- `_build_note_content(...)` arma la nota; `_update_index(...)` la enlaza al índice de su categoría.
- `ingest_playlist(...)` orquesta todo; `_main(argv)` es la CLI.
- **Tool (`tools/ingestion.py`):** `youtube_ingest_playlist`.

> ⚠️ **No probado end-to-end contra YouTube real** (el entorno de desarrollo tenía YouTube bloqueado por
> red): los tests corren con transcripciones/listados/LLM mockeados. Requiere una validación manual en la
> PC de Damian.

---

*Nota:* el vault de seguridad (`obsidian_vault/`) y el de investigación científica
(`obsidian_vault_investigacion/`) son dos vaults distintos con perfiles separados; ninguno se mezcla con
el vault Obsidian personal de Damian fuera del repo.
