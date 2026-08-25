# 04 · Auditoría de código: indexado, seguridad, calidad, fixes y verificación

El corazón "auditor" de Raphael. Patrón de dirección de dependencias: `app/tools/*.py` (wrappers finos
para el LLM) → paquetes de librería (`codebase`, `security`, `quality`, `findings`, `testing`,
`codeedit`, `selfrepair`) → nunca al revés. Los caches en disco nunca se escriben dentro del proyecto
auditado; van a `data/…` (ver [15](15-configuracion.md)).

---

## `app/codebase/` — indexado de proyectos en grafo

Indexa cualquier repo en un grafo de archivos/símbolos/imports. **Solo lectura, no sandboxeado**
(auditar un repo externo funciona aunque no esté en `FS_ALLOWED_ROOT`).

- **`models.py`** — `Symbol` (nombre, tipo, línea), `FileEntry` (ruta, lenguaje, símbolos),
  `LanguageStat`, `CodebaseIndex` (con `to_dict`/`from_dict`).
- **`languages.py`** — `detect_language(filename)` mapea extensión→lenguaje.
- **`indexer.py`** — `build_index(root)`: recorre archivos respetando `.gitignore`
  (`_load_gitignore_spec`, `_iter_files`), extrae símbolos con tree-sitter
  (`_extract_symbols_treesitter` vía `_grammar_resources`) y cae a un extractor por regex
  (`_extract_symbols_fallback`) cuando no hay gramática. `_index_file` produce un `FileEntry`.
- **`graph.py`** — construye las aristas de import reales. `_SuffixIndex` resuelve un import a un archivo
  del repo por sufijo de path; `_python_edges`/`_js_edges` extraen dependencias por lenguaje;
  `build_edges(index)` devuelve la lista de edges (archivo→archivo).
- **`store.py`** — cache JSON por proyecto en `CODEBASE_INDEX_DIR` (`_slug_for`/`_cache_path`).
  `get_or_build(root, refresh)`, `load_cached`, `save_cache`, `list_cached_projects`.
- **Tools (`tools/codebase.py`):** `codebase_index_project` (detecta lenguajes, arma el grafo),
  `codebase_search_symbol` (busca funciones/clases por nombre parcial), `codebase_file_outline`
  (lenguaje + símbolos de un archivo). Router HTTP asociado: `/api/codebase/*` (ver [11](11-servidor-fastapi.md)).

---

## `app/findings/` — modelo unificado de hallazgos

Compartido por seguridad y calidad, para no duplicar el modelo de "hallazgo".

- **`models.py`** — `Finding` (tool, file, line, rule_id, severidad, mensaje, tags; `to_dict`/`from_dict`),
  `make_finding_id(tool,file,line,rule_id)` (hash estable), `resolve_finding(...)` (ubica un hallazgo por
  file+rule_id+line, devolviendo líneas candidatas si el line no matchea), `candidate_lines(...)`,
  `ScanResult` (colección + metadata de la corrida).
- **`binaries.py`** — `tool_path(name)` (localiza un binario en PATH/venv), `node_shim_argv(...)` (arma la
  invocación de una herramienta Node empaquetada), `relpath`, `chunk_paths` (divide listas de archivos en
  batches por tamaño máximo de línea de comando).
- **`noise.py`** — `split_noise(findings)` separa hallazgos ruidosos de los reales.
- **`rescan.py`** — `merge_file_findings(...)` fusiona el re-escaneo de un archivo con el scan previo.
- **`runner_util.py`** — `run_scanner(...)` helper común para invocar un escáner externo.
- **`severity_index.py`** — `build_file_risk_index(root)` y `list_file_findings(root, file_rel)` cruzan
  seguridad + calidad por archivo con la severidad más alta (`_higher_severity`).

---

## `app/security/` — escaneo de seguridad real (SAST/SCA)

- **`scanners.py`** — un runner por herramienta, cada uno devuelve `list[Finding] | None`:
  `run_semgrep` (multi-lenguaje), `run_bandit` (Python), `run_cppcheck` (C/C++), `run_clang_tidy` (C/C++,
  requiere `compile_commands.json` — `find_compile_commands_dir`, `_detect_gnu_cross_target_args`),
  `run_trivy` (SCA/dependencias).
- **`runner.py`** — `scan_project(path, refresh)` orquesta todos los escáneres aplicables y cachea;
  `rescan_file(path, file)` re-escanea un solo archivo tras un fix.
- **`store.py`** — cache en `SECURITY_SCAN_DIR`: `save_scan`, `load_scan`, `find_finding`,
  `find_candidate_lines`.
- **`rule_categories.py`** — `category_for_rule(rule_id)` clasifica reglas en categorías (para el triage
  y las notas de referencia).
- **`triage.py`** — `triage_finding(root, finding)` / `triage_findings(root, findings)`: el LLM mira el
  **código real** alrededor de cada hallazgo (`_code_context`) más una nota de referencia y emite un
  `TriageVerdict` (`_parse_verdict`). Distingue verdadero positivo de ruido.
- **`triage_reference.py`** — `ensure_reference_notes()` crea notas de referencia por categoría en el
  vault; `get_reference_for_category(cat)` las recupera para inyectarlas al triage.
- **Tools (`tools/security_scan.py`):**
  - `security_scan_project` — corre los escáneres, cachea, devuelve hallazgos (recortados a 100/por
    tamaño).
  - `security_get_finding` — trae el código real alrededor de la línea **más** las notas de Obsidian
    relacionadas. Se pide por `file+rule_id+line` (no por un `finding_id` de memoria).
  - `security_audit_find_fix_verify` — **ciclo atómico**: aplica el fix, lo commitea, corre la suite de
    tests real y confirma si el hallazgo puntual quedó resuelto (`finding_resolved`). Acepta
    `requested_rule_id`/`requested_file` para rechazar a propósito si se intenta arreglar un hallazgo
    distinto del pedido (bug real 2026-08-09).
  - `security_triage_findings` — triage con criterio del LLM sobre hallazgos ya escaneados.

---

## `app/quality/` — calidad/bugs generales (no seguridad)

Mismo patrón que `security/`, cache separado (`QUALITY_SCAN_DIR`).

- **`scanners.py`** — `run_ruff` (+`_ruff_severity`, `_has_ruff_config`), `run_mypy` (solo si el código
  "parece tipado", `_looks_typed`), `run_eslint`, `run_tsc`, `run_detekt` (Kotlin). `_anchored_relpath`
  normaliza rutas.
- **`runner.py`** — `scan_project(path, refresh)` / `rescan_file(path, file)`.
- **`store.py`** — `save_scan`, `load_scan`, `find_finding`, `find_candidate_lines`.
- **Tools (`tools/quality_scan.py`):** `quality_scan_project`, `quality_get_finding`.

---

## `app/codeedit/` — aplicación de fixes reversibles

- **`fixer.py`** — `apply_fix(...)` reemplaza `old_snippet`→`new_snippet` en un archivo (falla con
  `SnippetNotFoundError`/`SnippetAmbiguousError` si el snippet no existe o es ambiguo). `_resolve_in_root`
  valida contra la raíz del repo pasado. `commit_if_eligible(root, file_rel, message)` commitea el cambio
  si el repo es git (`_is_git_repo`, `_git_commit_file`) — **cada fix queda en su propio commit,
  revertible**.
- **Tool (`tools/code_edit.py`):** `code_apply_fix` — patrón **dry-run → confirm=true**: con
  `confirm=false` muestra el diff; con `confirm=true` aplica y commitea. Es la vía para ediciones que el
  usuario quiere revisar antes de aplicar.

---

## `app/testing/` — corrida de tests reales

Cierra el gap "compiló ≠ funciona" antes de re-auditar.

- **`detect.py`** — `detect_test_command(root, index)` decide el comando de tests:
  `_python_test_command` (pytest si hay `test_*.py`), `_node_test_command`, `_gradle_test_command`.
- **`models.py`** — `DetectedCommand`, `RunOutcome` (exit_code, stdout/stderr, timed_out).
- **`runner.py`** — `run_tests(path, timeout)` corre la suite vía `shell_exec.run_shell_command`.
- **`store.py`** — cache de la última corrida por proyecto (`TEST_RUN_DIR`): `save_last_run`,
  `load_last_run`. Es lo que lee `audit_report` para marcar si hubo tests en verde tras los fixes.
- **Tool (`tools/test_run.py`):** `code_run_tests` — detecta y corre la suite real.

---

## `app/selfrepair/` — auto-reparación del propio backend (Opción C)

Raphael puede **proponer** un fix a su propio código, pero aplicarlo requiere confirmación humana con un
`proposal_id` concreto.

- **`models.py`** — `SelfFixProposal` (id `sf-xxxxxxxx`, file, old/new snippet, diff, timestamp).
- **`propose.py`** — `propose_fix(...)` genera la propuesta (dry-run, diff real, sin gate) y la adjunta a
  una nota del vault (`_attach_to_note`).
- **`store.py`** — persistencia en `SELFREPAIR_DIR`: `save_proposal`, `load_proposal`, `mark_applied`,
  `list_pending`.
- **`gate.py`** — el guardrail que corre en el loop del agente:
  - `generate_proposal_id()`, `extract_confirmed_proposal_ids(user_message)` (busca `sf-xxxxxxxx` en el
    mensaje **real** de Damian).
  - `is_self_target(resolved_path)` / `_resolve_target_path(tool_name, args)` — ¿la escritura apunta al
    propio `backend/`?
  - `self_target_gate_error(tool_name, args, user_message)` — **bloquea** toda escritura self-target
    salvo que el mensaje traiga un `proposal_id` que matchee una propuesta pendiente para ese mismo file y
    snippet (`_matching_pending_proposal`). `fs_write_file` sobre el propio código está bloqueado siempre.
  - `consume_proposal_if_applied(...)` — marca la propuesta como aplicada tras un `code_apply_fix
    confirm=true` exitoso, para que el id no se reuse.
- **Tool (`tools/selfrepair.py`):** `selfrepair_propose_fix` — solo propone. Aplicar de verdad se hace
  con `code_apply_fix confirm=true` + el `proposal_id` en el mensaje de Damian. Tras aplicar, el backend
  **sigue corriendo con el código viejo hasta que alguien lo reinicia**.

---

## `app/audit_report.py` — reporte de auditoría

Compila un Markdown legible (hallazgos abiertos de seguridad+calidad, fixes aplicados con su commit,
resumen ejecutivo) leyendo del cache de escaneos y del `audit_log` — no vuelve a correr escáneres ni
inventa qué se aplicó. Lo guarda como nota del vault (autor "jarvis"). Marca explícitamente si la última
corrida de tests quedó en verde. Tool: `audit_generate_report`.

---

## `app/introspection/` — meta-observación post-hoc (Opción B)

Analiza el `audit_log` de sesiones ya cerradas para detectar patrones de falla del propio agente.

- **`analyzer.py`** — `analyze_conversation(conversation_id, min_repeats)` / `analyze_all(...)`:
  `_find_repeated_identical_writes` (el loop de reescritura idéntica de v6) y
  `_find_abandoned_blocked_writes` (archivo bloqueado nunca reintentado, v5). Devuelve `Finding`s;
  `write_finding_note(finding)` los deja como nota en el vault. `_DEFAULT_MIN_REPEATS`=3 es el mismo
  umbral que el guardrail **en vivo** del agente (`_LIVE_LOOP_MIN_REPEATS`) — dos consumidores del mismo
  criterio, uno en vivo y otro post-hoc.
- **`run.py`** — `main(argv)` CLI para correr el análisis a mano.

---

*Segunda pasada sugerida:* documentar los formatos exactos de `Finding`/`ScanResult` en JSON y los
parámetros JSON Schema de cada tool.
