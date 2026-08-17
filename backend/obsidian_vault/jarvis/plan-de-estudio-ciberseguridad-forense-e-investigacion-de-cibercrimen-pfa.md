---
author: jarvis
category: forense-digital
created: '2026-08-13T01:47:39.869749+00:00'
tags:
- forense-digital
- plan-de-estudio
- pfa-ingreso
title: 'Plan de Estudio: Ciberseguridad Forense e Investigación de Cibercrimen (PFA)'
updated: '2026-08-13T01:47:39.869749+00:00'
---

## Cómo usar este plan

Este plan está armado con un método fijo, pensado específicamente para cómo venís aprendiendo el resto de Jarvis: **primero la analogía, después el concepto técnico, después el código real que lo implementa, después un ejercicio verificable**. Nunca al revés. Si en algún punto la analogía no te cierra o el ejercicio te parece trivial, es señal de que hay que pasar al siguiente nivel, no de saltearlo.

Arranca en básico-medio a propósito -- no asume que ya sabés qué es un hash o qué es un grafo. Cada nivel se apoya en el anterior. La progresión completa cubre, en orden: cadena de custodia → estándares forenses → marco legal argentino → metodología de investigación → hashing/firma digital → análisis de enlaces y timeline. Es la misma secuencia lógica de una investigación real: primero entendés las reglas del juego (qué hace válida una prueba), después la metodología para trabajar, y recién al final las técnicas analíticas más avanzadas (grafos, timelines) que se apoyan en que todo lo anterior esté bien hecho.

**Regla de oro de este plan**: cada concepto tiene que anclar en algo real y ejecutable del proyecto (`backend/app/investigation/`), no quedarse en teoría aislada. Ese módulo ES una implementación real, corriendo, de investigación forense/cibercrimen -- estudiar la teoría leyendo su código real es doblemente productivo: aprendés el concepto Y auditás/reforzás una herramienta que vas a poder seguir usando.

**Leyenda de ejercicios**:
- ✅ = listo para hacer ahora mismo, sin nada más que instalar.
- ⏳ = pendiente, requiere descargar datasets forenses públicos (NIST CFReDS / Digital Corpora) que **todavía no están configurados en esta sesión** -- no se marca como "hecho" hasta que esa infraestructura exista de verdad.

Todas las fuentes primarias de cada tema (NIST, ISO, Ley 26.388, SANS, etc.) están citadas en la nota específica de ese tema, linkeada al principio de cada sección -- no se duplican acá para evitar que dos copias de la misma cita queden desactualizadas de forma independiente.

---

## Nivel Básico

El objetivo de este nivel es UNA sola cosa: entender por qué una prueba digital técnicamente perfecta puede ser inútil en un proceso judicial si no está documentada y manejada correctamente. Todo lo demás del plan asume que esto ya está sólido.

### 1. Cadena de custodia digital

**Analogía primero**: pensá en la posta de una carrera de relevos. No alcanza con que el equipo corra rápido -- si un corredor deja caer el testimonio, lo levanta otro que no estaba autorizado, o nadie anota quién lo llevó en cada tramo, la carrera se anula aunque el tiempo final haya sido bueno. La cadena de custodia es exactamente eso aplicado a evidencia: no importa cuán íntegro sea el archivo en sí, si hay UN tramo sin documentar, la prueba completa puede quedar inadmisible.

**Nota completa**: [[Cadena de Custodia Digital]]

**Dónde está esto en código real**: en `backend/app/investigation/models.py`, la clase `Edge` (línea 155 en adelante) tiene dos campos obligatorios que son "cadena de custodia hecha schema": `confianza` (float 0-1) y `derivada_por` (`parser` | `modelo` | `manual`, línea 54-57). Ninguna arista del grafo de un caso puede existir sin decir de dónde salió y qué tan segura es esa afirmación -- es la misma exigencia que un formulario de cadena de custodia en papel, pero forzada por el tipo de dato, no por buena voluntad de quien carga los datos.

**Ejercicios**:
- ✅ Leer `models.py` completo (especialmente el docstring del módulo, líneas 1-21, y la clase `Edge`, líneas 155-208) y escribir en tus propias palabras qué garantiza en términos de cadena de custodia que `confianza` y `derivada_por` sean campos *obligatorios* de toda arista, nunca opcionales.
- ✅ Leer `case_store.py` y responder: ¿por qué no existe ninguna función `delete_node` o `delete_edge` en todo el módulo? Buscar la palabra `retract` y relacionarlo con el principio de que "ningún eslabón de la cadena puede desaparecer, solo puede marcarse como corregido".
- ✅ Correr la suite de tests de `case_store` y explicar, test por test, qué garantía de cadena de custodia prueba cada uno:
  ```
  cd C:\Users\dam\Documents\JarvisRemote\backend
  .venv\Scripts\python.exe -m pytest tests/test_investigation_case_store.py -v --timeout=60
  ```
  Prestar especial atención a `test_retract_node_marks_it_without_deleting` y `test_retract_edge_never_touches_the_underlying_nodes`.

### 2. Estándares forenses: NIST SP 800-86 e ISO/IEC 27037

**Analogía primero**: es la diferencia entre una receta de cocina estandarizada (los mismos pasos, en el mismo orden, dan el mismo resultado reproducible en cualquier cocina) y cocinar "a ojo". Un estándar forense no es burocracia -- es lo que permite que dos peritos distintos, en dos momentos distintos, lleguen al mismo resultado analizando la misma evidencia, y que un tercero pueda auditar el proceso sin haber estado presente.

**Nota completa**: [[Estándares Forenses: NIST SP 800-86 e ISO/IEC 27037]]

**Dónde está esto en código real**: las 4 fases de NIST SP 800-86 (Recolección → Examen → Análisis → Reporte) tienen un correlato directo y verificable en `app/investigation/`:
- **Recolección** → `artifact_store.store_artifact`, invocado desde `csv_parser.ingest_csv` (línea 97 de `csv_parser.py`) -- calcula el hash del artefacto en el momento de guardarlo, igual que un write blocker calcula el hash al adquirir.
- **Examen** → `csv_parser.make_node_from_row` y `ner.propose_entities` -- extraen datos estructurados de la evidencia cruda (fila de CSV, texto libre) sin todavía sacar conclusiones.
- **Análisis** → `graph_metrics.py` (centralidad, detección de pivotes) y `timeline.py` (cronología, contradicciones) -- ver Nivel Avanzado.
- **Reporte** → el log firmado (`log.jsonl`) más el estado materializado en git son, juntos, el reporte auditable de todo lo que se hizo y por qué.

**Ejercicios**:
- ✅ Armar vos mismo, por escrito, la tabla completa "fase NIST → archivo(s) real(es) de `app/investigation/` → qué hace concretamente ese archivo en esa fase" -- la de arriba es un punto de partida incompleto a propósito, completala con tu propia lectura del código.
- ✅ Leer el docstring de `csv_parser.py` (líneas 1-21) y responder: ¿qué proceso de ISO/IEC 27037 (Identificación / Recolección / Adquisición / Preservación) corresponde a que el nodo `Archivo` tenga id determinístico por su propio sha256 (ver `models.make_archivo`, línea 250 de `models.py`)? Justificar con el texto del estándar citado en la nota de estándares.

### 3. Marco legal argentino: Ley 26.388 y Protocolo Federal de Evidencia Digital

**Analogía primero**: un hash perfecto y una cadena de custodia impecable son como tener las pruebas de ADN perfectas de una escena -- pero si se recolectaron sin orden judicial en un allanamiento sin autorización, un juez las puede descartar igual. La técnica perfecta no reemplaza el marco legal: son dos capas independientes, y las dos tienen que sostenerse para que la evidencia sirva.

**Nota completa**: [[Marco Legal Argentino: Ley 26.388 y Protocolo Federal de Evidencia Digital]]

**Dónde conecta con el proyecto**: el art. 77 del Código Penal (incorporado por la Ley 26.388) define "documento" y "firma" en su forma digital -- es el fundamento legal argentino de por qué una firma Ed25519 real (ver Nivel Intermedio, sección 5) puede valer como firma. Y el hecho de que `case_store.rebuild_from_log` (línea 189 de `case_store.py`) pueda reconstruir el estado completo de un caso *solo* a partir del log, verificando la cadena antes de confiar en ella, es la prueba técnica concreta de la reconstructibilidad y trazabilidad que exige el Protocolo Federal de Evidencia Digital 2023.

**Ejercicios**:
- ✅ Leer el texto de los artículos 153 bis (acceso no autorizado) y 173 inciso 16 (fraude informático) en la fuente oficial ya citada en la nota de marco legal, y escribir en tus palabras la diferencia entre ambos, con un ejemplo hipotético *genérico* de cada uno (nunca un caso real ni una persona real).
- ✅ Leer el docstring de `case_store.py` (líneas 1-20) y `rebuild_from_log` completo (líneas 189-226), y responder por escrito: ¿por qué que el caso sea "reconstruible desde cero a partir del log" es relevante para el estándar de cadena de custodia que exige el protocolo? ¿Qué pasaría si `rebuild_from_log` confiara en un log sin verificar la firma primero?

---

## Nivel Intermedio

Con básico sólido (sabés qué hace válida una prueba y bajo qué marco legal), este nivel es sobre CÓMO se investiga en la práctica -- metodología de trabajo y el mecanismo criptográfico exacto que sostiene todo lo del nivel básico.

### 4. Metodología de investigación de cibercrimen

**Analogía primero**: PICERL (Preparación → Identificación → Contención → Erradicación → Recuperación → Lecciones Aprendidas) es como el protocolo de un bombero en un incendio: apagar el fuego rápido (contención) no es lo mismo que investigar qué lo causó (forense) -- a veces incluso están en tensión (apagar rápido puede destruir evidencia de la causa). Un buen investigador sabe cuándo está haciendo cada cosa y por qué no son intercambiables.

**Nota completa**: [[Metodologías de Investigación de Cibercrimen]]

**Dónde está esto en código real**: `ner.py` implementa, de forma muy literal, el principio de que la identificación de una entidad NUNCA es automática/definitiva -- toda propuesta de NER queda en estado `"pendiente"` (ver `EntityProposal.status`, línea 102) hasta que un humano la confirma o rechaza explícitamente vía `confirm_proposal`/`reject_proposal` (líneas 315-374). Es la versión concreta de "Identification" como fase distinta y separada de "Analysis" que vos das por dado en PICERL.

**Ejercicios**:
- ✅ Leer el docstring completo de `ner.py` (líneas 1-43), especialmente el punto 2 ("ninguna propuesta entra al grafo sola"), y explicar por qué esto es un ejemplo concreto de que la fase de Identificación de una entidad nunca puede saltarse a Análisis sin revisión humana.
- ✅ Correr la suite de tests de NER, leer los nombres de cada test y, para al menos 4 de ellos, escribir qué principio de la metodología (identificación vs. confirmación, trazabilidad, descarte no silencioso de candidatos inválidos) está probando:
  ```
  cd C:\Users\dam\Documents\JarvisRemote\backend
  .venv\Scripts\python.exe -m pytest tests/test_investigation_ner.py -v --timeout=60
  ```
- ✅ Leer la sección "OSINT ético y sus límites legales" de la nota de metodología, y escribir en tus palabras la distinción entre OSINT legítimo y acceso no autorizado -- esta distinción es la que vas a tener que aplicar sin excepción en cualquier ejercicio futuro con datos reales.

### 5. Hashing y firma digital: integridad y no repudio

**Analogía primero**: el hash es como el sello de garantía de un frasco de remedios -- si está roto, sabés que algo pasó, aunque no sepas quién lo rompió. La firma digital es distinta: es como una firma notarial sobre ese sello -- no solo dice "esto no fue tocado", dice "y fue *esta persona específica*, con *esta clave específica*, quien lo selló", de forma que ni siquiera esa persona puede después negar creíblemente haberlo hecho.

**Nota completa**: [[Hashing SHA-256 y Firma Digital: Integridad y No Repudio en Evidencia Digital]]

**Dónde está esto en código real**, con el mayor detalle de todo el plan porque es la pieza más técnica del módulo:
- `app/investigation/log.py` implementa **las dos garantías juntas, explícitamente separadas** en su docstring (líneas 1-27): encadenamiento por hash (`prev_hash`/`entry_hash`, tamper-evidence) Y firma Ed25519 (`signature`, autenticidad) -- ninguna sustituye a la otra. `verify_chain` (línea 132) recorre toda la cadena desde el génesis y corta en la primera falla, verificando las tres cosas: hash recalculado, encadenamiento con la entrada anterior, y firma válida.
- `app/investigation/keys.py` es la decisión real de dónde vive la clave privada: cifrada con DPAPI (Windows Data Protection API), atada a la cuenta de Windows de esta máquina. El docstring del módulo completo (líneas 1-50) es, literalmente, un documento de decisión de diseño con alternativas consideradas y descartadas -- vale leerlo entero como ejercicio de "cómo se documenta una decisión criptográfica real", no solo por el contenido técnico.

**Ejercicios**:
- ✅ Leer el docstring de `log.py` (líneas 1-27) y explicar con tus propias palabras la diferencia entre tamper-evidence (hash chain) y autenticidad (firma) -- ¿por qué alguien SIN la clave privada podría, en teoría, reescribir el archivo entero con una cadena de hashes nueva y consistente, pero igual sería detectado por `verify_chain`?
- ✅ Correr la suite completa de tests del log, y para los tres tests que simulan un ataque distinto a propósito, escribir qué tipo de manipulación de evidencia real está simulando cada uno:
  ```
  cd C:\Users\dam\Documents\JarvisRemote\backend
  .venv\Scripts\python.exe -m pytest tests/test_investigation_log.py -v --timeout=60
  ```
  Los tres a mirar en detalle: `test_verify_chain_detects_payload_tampering`, `test_verify_chain_detects_a_deleted_middle_entry`, `test_verify_chain_detects_a_forged_entry_with_correct_hash_chain_but_no_real_signature`.
- ✅ Leer el docstring completo de `keys.py` (líneas 1-50) y responder por escrito: ¿por qué DPAPI y no pedir una passphrase en cada arranque? Según las líneas 36-44, si la clave privada se corrompe o se pierde, ¿qué se pierde exactamente y qué NO se pierde?
- ✅ Correr la suite de tests de `keys.py` y verificar en particular que `test_private_key_file_is_dpapi_encrypted_not_plaintext_key_material` prueba justo la propiedad que el docstring promete (clave privada nunca en texto plano en disco):
  ```
  .venv\Scripts\python.exe -m pytest tests/test_investigation_keys.py -v --timeout=60
  ```

---

## Nivel Avanzado

Este es el nivel más técnicamente demandante del plan -- asume que básico e intermedio ya están sólidos. Es donde la investigación deja de ser "un caso a la vez" y pasa a ser análisis estructural sobre TODO el caso junto: patrones que ningún elemento aislado muestra por sí solo.

### 6. Análisis de enlaces y timeline forense

**Analogía primero, centralidad de intermediación**: en una red de rutas entre ciudades, la ciudad con más autopistas no es necesariamente la más importante estratégicamente -- la que de verdad importa es la que está *en el medio del único camino* entre dos regiones que si no, no tendrían forma de conectarse. Cortarla corta la red en dos. Eso es exactamente lo que mide la centralidad de intermediación (betweenness centrality) sobre un grafo de investigación: no quién tiene más conexiones, sino quién es el puente obligado.

**Analogía primero, contradicciones de timeline**: es el clásico interrogatorio de coartada -- "decís que estabas en la oficina a las 14:05 y también que estabas en tu casa a las 14:07, y la oficina y tu casa están a 40 minutos" no prueba que mientas, pero es una bandera roja que un investigador humano tiene que revisar, nunca algo que el sistema debe "resolver solo".

**Nota completa**: [[Análisis de Enlaces y Normalización de Timeline Forense]]

**Dónde está esto en código real**:
- `app/investigation/graph_metrics.py` calcula betweenness centrality real (vía `networkx`, línea 54) sobre el grafo de nodos/aristas vigentes de un caso -- el docstring del módulo (líneas 1-23) explica por escrito, con la misma lógica de la analogía de arriba, por qué se eligió esta métrica y no degree centrality (cantidad simple de conexiones). También calcula `compute_confidence` (línea 57): el promedio de confianza de las aristas incidentes a cada nodo, la "confianza estructural" de una entidad dentro del caso.
- `app/investigation/timeline.py` normaliza timestamps heterogéneos a UTC (`normalize_timestamp`, línea 26) con una decisión de diseño documentada en el propio docstring sobre por qué Argentina usa DD/MM y eso rompe el default de `dateutil` (MM/DD), y `detect_contradictions` (línea 124) implementa exactamente la analogía de la coartada: misma entidad, dos nodos Host distintos, timestamps demasiado cerca -- señalado para revisión humana, nunca resuelto automáticamente.

**Ejercicios**:
- ✅ Leer `graph_metrics.py` completo (es corto, ~78 líneas) y explicar en tus palabras, sin copiar el docstring, por qué betweenness centrality captura "candidato a pivote" mejor que contar conexiones simples.
- ✅ Ejercicio de predicción antes de verificar: leer el test `test_centrality_identifies_the_real_bridge_node_in_a_path_graph` (archivo `tests/test_investigation_graph_metrics.py`), dibujar A MANO en papel el grafo que ese test arma, y marcar vos mismo qué nodo debería tener mayor centralidad ANTES de correr el test. Después correr y verificar tu predicción:
  ```
  cd C:\Users\dam\Documents\JarvisRemote\backend
  .venv\Scripts\python.exe -m pytest tests/test_investigation_graph_metrics.py -v --timeout=60
  ```
- ✅ Leer `detect_contradictions` completo (líneas 124-166 de `timeline.py`) y responder por escrito el criterio EXACTO que usa (qué campos compara, qué ventana de tiempo, qué tipo de arista mira) -- y por qué la función deliberadamente nunca decide cuál de las dos conexiones es la real.
- ✅ Correr la suite completa de tests de timeline y mapear cada test a un concepto de metodología forense de timeline (normalización a UTC, formato ambiguo DD/MM vs MM/DD, exclusión de elementos retractados, ventana configurable de contradicción):
  ```
  .venv\Scripts\python.exe -m pytest tests/test_investigation_timeline.py -v --timeout=60
  ```

### 7. Ejercicio integrador (capstone del plan)

- ✅ Seguir a mano, leyendo el código en orden, el camino completo de una fila de un CSV ingerido hasta convertirse en evidencia auditable: `csv_parser.ingest_csv` (guarda el artefacto y su hash) → `case_store.add_node` (persiste el nodo + arista `aparece_en`) → `log.append_entry` (encadena por hash) → `keys.sign` (firma Ed25519). Dibujar el diagrama de ese flujo (papel o una nota nueva en este vault) y anotar, en cada paso, qué estándar o concepto de este plan aplica ahí (ISO 27037 adquisición, cadena de custodia, hashing, firma digital, versionado git). Este ejercicio es el que demuestra si de verdad conectaste los 6 temas del plan entre sí, no solo cada uno por separado.

---

## Qué falta / Pendiente

Ejercicios que **requieren datos reales de un dataset forense público** (NIST CFReDS o Digital Corpora -- los únicos datasets aceptables según el propio spec del módulo de investigación, nunca datos de personas reales) y que **todavía no están listos para hacerse hoy**, porque esa infraestructura no está configurada en esta sesión:

- ⏳ Descargar una imagen forense de práctica de NIST CFReDS o Digital Corpora, calcular su hash SHA-256 y compararlo contra el hash publicado por la fuente -- ejercicio real de verificación de integridad, no simulado.
- ⏳ Ingestar un CSV de ejemplo de un dataset público (Digital Corpora) al módulo de investigación vía `csv_parser.ingest_csv`, contra un caso de prueba armado específicamente para esto, y verificar que las trazas `aparece_en` apuntan al nodo `Archivo` correcto.
- ⏳ Armar un timeline con datos multi-fuente reales (logs con timezones distintas) de un dataset público de DFIR y usar `timeline.build_timeline` + `detect_contradictions` sobre datos reales en vez de los fixtures sintéticos de los tests.

Estos tres quedan marcados explícitamente como pendientes -- no se resuelven leyendo código ni corriendo la suite de tests existente, necesitan que primero se descargue y prepare el dataset. Ese es un paso de infraestructura aparte, no cubierto por este plan de estudio.

**Límite honesto de este plan**: el nivel avanzado de análisis forense de red (network forensics, captura y análisis de tráfico real) y el detalle interno de procedimiento de la División Cibercrimen de la PFA quedan fuera de este plan -- la nota de metodología ya documenta explícitamente que no se encontraron fuentes públicas confiables sobre el procedimiento interno de la PFA más allá del protocolo federal citado, y no corresponde inventar ese detalle acá tampoco.