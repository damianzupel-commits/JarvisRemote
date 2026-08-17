import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    api_key: str = os.getenv("API_KEY") or secrets.token_urlsafe(32)
    _api_key_was_generated: bool = not os.getenv("API_KEY")

    lmstudio_base_url: str = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    lmstudio_model: str = os.getenv("LMSTUDIO_MODEL", "local-model")

    # Bug real 2026-08-10 (v6, sesión de creación del mod de Fabric): el cliente
    # OpenAI (app/llm_client.py) no tenía timeout explícito -- el SDK usaba su
    # default (600s), que una generación real lenta (cold start del modelo +
    # ~2800 tokens a ~4.4 tok/s) superó, disparando un reintento automático que
    # obligó a reprocesar el prompt completo (~21.6K tokens) desde cero.
    # Generoso a propósito: mejor esperar de más que cortar una generación real
    # en curso y forzar un reprocesamiento carísimo.
    llm_request_timeout_seconds: float = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "1800"))

    # Server + modelo de embeddings para memoria semántica del vault (ver
    # app/obsidian/embeddings.py). A propósito NO reusa LMSTUDIO_BASE_URL:
    # en esta máquina esa variable en realidad apunta a Ollama (puerto 11434,
    # el LLM de chat real -- el nombre "lmstudio" quedó de una migración
    # anterior, ver LMSTUDIO_BASE_URL de más arriba), que no tiene un modelo
    # de embeddings cargado. El LM Studio real (la app, puerto 1234 por
    # default) corre aparte y sí lo tiene -- confirmado real en esta PC el
    # 2026-07-30 (`curl localhost:1234/v1/embeddings` responde, Ollama
    # devuelve 404 "model not found" para el mismo pedido).
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "http://127.0.0.1:1234/v1")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5")

    fs_allowed_root: str = os.getenv("FS_ALLOWED_ROOT", str(Path.home()))
    fs_allow_delete: bool = _bool(os.getenv("FS_ALLOW_DELETE"), False)

    browser_headless: bool = _bool(os.getenv("BROWSER_HEADLESS"), False)

    # Control de escritorio (mouse/teclado/ventanas de cualquier app, ver
    # app/tools/desktop.py) es tan invasivo como el Accessibility Service del
    # celular. Prendido por default porque el usuario pidió explícitamente la
    # versión sin fricción, pero queda como flag real para poder apagarlo.
    desktop_control_enabled: bool = _bool(os.getenv("DESKTOP_CONTROL_ENABLED"), True)

    # Ejecución de comandos de shell reales en la PC (ver app/tools/pc_command.py::
    # pc_run_command) -- análogo directo de PHONE_SHELL_ENABLED pero del lado de la
    # PC: código/comandos arbitrarios (pip install, pytest, npm, git, etc.), no solo
    # tools puntuales. Mismo criterio que DESKTOP_CONTROL_ENABLED/PHONE_SHELL_ENABLED
    # (usuario ya pidió explícitamente la versión sin fricción, prendido por default),
    # pero queda como flag real para poder apagarlo sin tocar código.
    pc_shell_enabled: bool = _bool(os.getenv("PC_SHELL_ENABLED"), True)

    max_agent_iterations: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))

    # Tope de iteraciones extendido, SOLO para tareas que resultan ser creación de
    # código multi-archivo -- ver app/agent.py::run_agent, se activa recién cuando
    # el turno actual ya usó fs_write_file al menos una vez (no es un default
    # general: una auditoría o un chat normal nunca llega a necesitarlo). Bug real
    # 2026-08-10: crear un mod de Fabric desde cero (build.gradle, fabric.mod.json,
    # varias clases Java, tags, lang, modelos) agotó las 30 iteraciones por defecto
    # antes de terminar de armar el wrapper de Gradle o intentar compilar.
    max_agent_iterations_code_task: int = int(os.getenv("MAX_AGENT_ITERATIONS_CODE_TASK", "50"))

    # Tope de mensajes que se guardan por conversación en memoria (ver
    # app/agent.py::_trim_history). Sin esto, `_conversations` crece para
    # siempre mientras el proceso esté vivo y termina superando el contexto
    # del modelo (pasó de verdad: "Context size has been exceeded" de LM
    # Studio, todo /api/chat empezó a tirar 500). El corte es simple —por
    # cantidad de mensajes, no por tokens reales— y siempre cae en el próximo
    # mensaje 'user' para no partir un tool_call de su respuesta.
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "40"))

    # Tope de tamaño (caracteres del JSON serializado, proxy barato de tokens ya que
    # no tenemos el tokenizer real del modelo cargado) para el contenido de UN SOLO
    # mensaje 'tool' antes de mandarlo al modelo (ver app/agent.py::_cap_tool_result).
    # Bug real encontrado 2026-08-03: security_scan_project sobre un proyecto con
    # cientos de hallazgos (ej. pygoat, 312 hallazgos) devuelve ~47KB de JSON en un
    # solo tool result -- sumado al system prompt (~9.7KB) y al schema de las ~50
    # tools registradas (~40KB), eso ya eran ~98KB (~28k tokens estimados) contra un
    # n_ctx real de 16384 tokens en Ollama para jarvis-text-v2 (confirmado con
    # `ollama show jarvis-text-v2`, ver server.log de Ollama: n_ctx = 16384, la
    # PRIMERA llamada del turno -- solo system+tools+mensaje del usuario, sin ningún
    # tool result todavía -- ya consumía 12546 tokens, dejando ~3800 de margen real).
    # Con el prompt así de sobrepasado, el context-shift de llama.cpp/Ollama
    # descarta el prompt viejo (deja solo n_keep=4 tokens del principio, ver log:
    # "n_keep = 4") para hacer lugar al tool result gigante -- así se pierde el
    # system prompt Y el pedido original del usuario, y el modelo, sin ese marco,
    # respondía con una introducción genérica ("Hola, soy Jarvis...") en vez de
    # seguir razonando sobre hallazgos que ya no podía "ver". _trim_history ya poda
    # por CANTIDAD de mensajes, pero no protege contra que UN SOLO mensaje sea
    # gigante -- este tope aparte cubre ese caso.
    max_tool_result_chars: int = int(os.getenv("MAX_TOOL_RESULT_CHARS", "6000"))

    # Presupuesto REAL de contexto del modelo, en tokens (ver app/agent.py::
    # _history_char_budget). Bug real encontrado 2026-08-09: con 51 tools ya
    # registradas, el system prompt (~9.7KB) + el schema de tools (~42KB) solos ya
    # representan ~13-16k tokens estimados -- contra un num_ctx de 16384, eso deja
    # margen CASI NULO para el historial de la conversación, y `_trim_history`
    # (que poda por CANTIDAD de mensajes) + `_cap_tool_result` (que acota UN SOLO
    # mensaje) no alcanzan a evitarlo: varios tool results medianos, cada uno bajo
    # su propio tope individual, igual suman más de lo que queda de contexto.
    # Un pedido real (security_scan_project sobre pygoat) llegó a 16372/16384
    # tokens de prompt, tardó varios MINUTOS solo en el prompt-processing (el
    # throughput se degrada con el contexto en este hardware, GPU de 12GB
    # compartida con CPU) y nunca llegó a generar respuesta. Subimos num_ctx a
    # 32768 en el Modelfile de Ollama (había VRAM/RAM de sobra, 24GB+ libres tras
    # liberar el pedido colgado) para dar aire real, pero el límite de acá es la
    # protección de fondo -- tiene que quedar sincronizado con el num_ctx real del
    # modelo cargado (no hay forma de leerlo del backend en runtime sin pegarle a
    # la API de Ollama aparte, así que es config manual).
    model_context_tokens: int = int(os.getenv("MODEL_CONTEXT_TOKENS", "32768"))

    # Tokens que se reservan SIN TOCAR para que el modelo pueda generar una
    # respuesta real después de "leer" todo el prompt -- si el presupuesto de
    # historial no descuenta esto, un prompt que llena el contexto hasta el
    # límite exacto no deja lugar para la respuesta (llama.cpp/Ollama hace
    # context-shift y tira el system prompt, ver nota de MAX_TOOL_RESULT_CHARS).
    reserved_response_tokens: int = int(os.getenv("RESERVED_RESPONSE_TOKENS", "3000"))

    # No tenemos el tokenizer real del modelo cargado en el backend -- estimar
    # tokens contando caracteres y dividiendo por esto. 3.2 es conservador
    # (subestima cuántos caracteres entran por token) a propósito: JSON de tool
    # results/schemas es denso en símbolos/comillas, más cerca de 3-3.5 chars/token
    # que las ~4 típicas de prosa en inglés -- mejor quedarse corto en el
    # presupuesto que volver a exceder el contexto real.
    chars_per_token_estimate: float = float(os.getenv("CHARS_PER_TOKEN_ESTIMATE", "3.2"))

    phone_tool_timeout: float = float(os.getenv("PHONE_TOOL_TIMEOUT", "30"))

    # Ejecución de comandos de shell reales en el celular vía Termux
    # (ver app/tools/phone.py::phone_run_command). Es el nivel más invasivo
    # posible del lado del celular: código arbitrario, no solo interacción con
    # la UI. Prendido por default (mismo criterio que DESKTOP_CONTROL_ENABLED:
    # el usuario ya pidió explícitamente la versión sin fricción), pero queda
    # como flag real para poder apagarlo sin tocar código.
    phone_shell_enabled: bool = _bool(os.getenv("PHONE_SHELL_ENABLED"), True)

    # Uso de la cámara del celular (ver app/tools/phone.py::phone_take_photo). Captura
    # silenciosa (sin abrir la app de Cámara), en la misma categoría de invasividad que
    # el resto de las tools de celular. Prendido por default (mismo criterio que
    # DESKTOP_CONTROL_ENABLED/PHONE_SHELL_ENABLED), pero queda como flag real para
    # poder apagarlo sin tocar código.
    phone_camera_enabled: bool = _bool(os.getenv("PHONE_CAMERA_ENABLED"), True)

    # Extracción de frames de video (ver app/video_frames.py y app/tools/phone.py::
    # phone_record_video) — no depende de PHONE_CAMERA_ENABLED por separado, la tool
    # de video usa la misma cámara y el mismo flag que la foto.
    video_frame_interval_seconds: float = float(os.getenv("VIDEO_FRAME_INTERVAL_SECONDS", "1.5"))
    video_max_frames: int = int(os.getenv("VIDEO_MAX_FRAMES", "8"))

    # TLS para servir wss:// en vez de ws:// (la conexión hoy viaja en texto
    # plano — ver sección de seguridad de README.md). Preparado pero apagado
    # por default a propósito: activarlo cambia la URL que espera la app del
    # celular (https:// en vez de http://) y requiere que Android confíe en el
    # certificado self-signed (ver `certs/README.md`) — un corte que hay que
    # coordinar con el usuario presente, no activar solo. Generar el cert con
    # `certs/generate_cert.sh` (o el comando equivalente documentado ahí).
    tls_enabled: bool = _bool(os.getenv("TLS_ENABLED"), False)
    tls_cert_path: str = os.getenv("TLS_CERT_PATH", str(Path(__file__).resolve().parent.parent / "certs" / "cert.pem"))
    tls_key_path: str = os.getenv("TLS_KEY_PATH", str(Path(__file__).resolve().parent.parent / "certs" / "key.pem"))

    # Archivo donde `jarvis_reflect` persiste reflexiones/decisiones abstraídas
    # (ver app/tools/reflect.py) — un JSONL append-only, no pasa por el sandbox
    # de FS_ALLOWED_ROOT porque es estado interno del backend, no un archivo
    # del usuario.
    reflections_path: str = os.getenv(
        "REFLECTIONS_PATH", str(Path(__file__).resolve().parent.parent / "reflections.jsonl")
    )

    # generate_video (ver app/tools/video_gen.py): dónde vive la instalación
    # portable de ComfyUI y en qué URL escucha su API HTTP. Default apunta a la
    # instalación de este equipo -- en otra máquina hay que ajustar COMFYUI_DIR
    # en el .env.
    comfyui_dir: str = os.getenv("COMFYUI_DIR", r"E:\ComfyUI\ComfyUI_windows_portable")
    comfyui_base_url: str = os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188")
    comfyui_startup_timeout: float = float(os.getenv("COMFYUI_STARTUP_TIMEOUT", "240"))
    # El Python embebido de la instalación portable (python_embeded/) trae un build
    # de PyTorch+ROCm que crashea (access violation real, reproducido con
    # torch.cuda.is_available()) en esta GPU no soportada oficialmente (gfx1031).
    # El venv separado `env_rocm/` (creado a mano durante el setup original) tiene
    # una versión de torch/ROCm que sí detecta la GPU sin crashear -- ese es el que
    # hay que usar para levantar el server. Configurable por si en otra instalación
    # el nombre/ubicación del venv que sí funciona es distinto.
    comfyui_python_path: str = os.getenv(
        "COMFYUI_PYTHON_PATH", r"E:\ComfyUI\ComfyUI_windows_portable\env_rocm\Scripts\python.exe"
    )

    # API nativa de Ollama (no la OpenAI-compatible de LMSTUDIO_BASE_URL) --
    # generate_video/generate_image la usan para descargar/recargar el modelo de
    # texto de la VRAM antes/después de generar, ya que compiten por la misma GPU.
    ollama_native_base_url: str = os.getenv("OLLAMA_NATIVE_BASE_URL", "http://127.0.0.1:11434")

    # generate_image (Flux.1 Schnell, un solo KSampler de 4 pasos) es más liviano que
    # generate_video, pero se deja igual un margen generoso por la misma variabilidad
    # de RAM/swapping observada en esta máquina.
    comfyui_generation_timeout_image: float = float(os.getenv("COMFYUI_GENERATION_TIMEOUT_IMAGE", "600"))

    # Cache en disco de índices de codebase (ver app/codebase/store.py) -- nunca
    # escribe dentro del proyecto que se indexa, un JSON por proyecto acá.
    codebase_index_dir: str = os.getenv(
        "CODEBASE_INDEX_DIR", str(Path(__file__).resolve().parent.parent / "data" / "codebase_index")
    )

    # Vault de notas estilo Obsidian (ver app/obsidian/vault.py) -- reemplazo
    # más rico de jarvis_reflect para notas con autor (jarvis/humano), tags y
    # wikilinks. Son archivos .md reales con frontmatter YAML, abribles con
    # Obsidian de verdad si el usuario quiere.
    obsidian_vault_path: str = os.getenv(
        "OBSIDIAN_VAULT_PATH", str(Path(__file__).resolve().parent.parent / "obsidian_vault")
    )

    # Índice de embeddings del vault (ver app/obsidian/embeddings.py) -- un
    # único JSON {note_id: vector}, nunca dentro del vault (que se abre con
    # Obsidian de verdad y parte de él se publica en git, ver .gitignore).
    # Mismo criterio que CODEBASE_INDEX_DIR/SECURITY_SCAN_DIR: cache derivado,
    # se puede borrar y reconstruir con `vault.reindex_all()`.
    obsidian_embeddings_path: str = os.getenv(
        "OBSIDIAN_EMBEDDINGS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "obsidian_embeddings.json")
    )

    # Cache en disco del último escaneo de seguridad por proyecto (ver
    # app/security/store.py) -- mismo criterio que CODEBASE_INDEX_DIR, nunca
    # escribe dentro del proyecto escaneado.
    security_scan_dir: str = os.getenv(
        "SECURITY_SCAN_DIR", str(Path(__file__).resolve().parent.parent / "data" / "security_scans")
    )

    # Cache en disco del último escaneo de CALIDAD (bugs generales, no
    # seguridad) por proyecto (ver app/quality/store.py) -- mismo criterio que
    # SECURITY_SCAN_DIR, carpeta separada para no mezclar los dos tipos de
    # hallazgo en el mismo cache.
    quality_scan_dir: str = os.getenv(
        "QUALITY_SCAN_DIR", str(Path(__file__).resolve().parent.parent / "data" / "quality_scans")
    )

    # Cache en disco de la ÚLTIMA corrida de tests reales por proyecto (ver
    # app/testing/store.py) -- mismo criterio que SECURITY_SCAN_DIR. Es lo que
    # lee `audit_report.generate_report` para marcar explícitamente si hubo (o
    # no) una corrida de tests real en verde después de los fixes aplicados,
    # en vez de asumir "compiló" == "funciona" (gap real 2026-08-10, ver
    # sesión de meta-observación: el pipeline nunca tenía un paso de
    # verificación funcional entre corregir y re-auditar).
    test_run_dir: str = os.getenv(
        "TEST_RUN_DIR", str(Path(__file__).resolve().parent.parent / "data" / "test_runs")
    )

    # Store de propuestas de auto-reparación (ver app/selfrepair/, agregado
    # 2026-08-11 -- Opción C del diseño de auto-reparación: Jarvis puede
    # PROPONER (dry-run, sin gate) un fix a su propio código, pero aplicarlo
    # de verdad (confirm=true) requiere un proposal_id concreto que Damian
    # confirme a mano -- ver el guardrail de self-target en agent.py). Cada
    # propuesta queda acá hasta que se aplica o se descarta.
    selfrepair_dir: str = os.getenv(
        "SELFREPAIR_DIR", str(Path(__file__).resolve().parent.parent / "data" / "selfrepair")
    )

    # nmap_scan (ver app/tools/network_scan.py + app/network/) -- reconocimiento
    # de RED real (puertos, servicios, versiones, vulnerabilidades NSE), a
    # diferencia de TODO el resto del pipeline (Semgrep/Bandit/cppcheck/
    # clang-tidy/Trivy/Ruff/mypy/ESLint/tsc), que es SAST/SCA puro y solo lee
    # código/manifiestos en disco, nunca toca una red real. Prendida por
    # default porque el guardrail de scope (app/network/guardrail.py) ya la
    # hace segura por diseño -- por default SOLO puede escanear rangos
    # privados/reservados y Tailscale, nunca una IP pública, sin importar este
    # flag. Poner en false desactiva la tool nmap_scan por completo sin tocar
    # código, por si el usuario prefiere no exponerla ni siquiera con el
    # guardrail de scope activo.
    nmap_enabled: bool = _bool(os.getenv("NMAP_ENABLED"), True)

    # Whitelist explícita de IPs/rangos PÚBLICOS (o cualquier otro por fuera del
    # scope privado/loopback/Tailscale) autorizados para nmap_scan -- coma-
    # separado, cada entrada una IP suelta o un CIDR (ej.
    # "203.0.113.10,203.0.113.0/24"). VACÍO por default a propósito: el USUARIO
    # tiene que llenar esto a mano, en su propio backend/.env, con
    # infraestructura que sea suya o para la que tenga autorización explícita
    # de escanear -- ni nmap_scan ni el LLM pueden agregarse un target nuevo
    # acá por ningún argumento de la tool call (ver app/network/guardrail.py).
    # Escanear una IP/dominio público sin autorización explícita del dueño
    # puede ser ilegal (leyes de acceso no autorizado / computer fraud en la
    # mayoría de países).
    nmap_authorized_targets: str = os.getenv("NMAP_AUTHORIZED_TARGETS", "")

    # Fuente ÚNICA y compartida de autorización para TODAS las tools de
    # pentesting activo (nmap_scan ya migrado; sqlmap/tshark/metasploit/zap/
    # nessus la reusan según se van agregando, ver app/network/guardrail.py) --
    # decisión de Damian 2026-08-13: un solo archivo en vez de una whitelist
    # separada por tool, para no tener 6 listas que se puedan desincronizar.
    # Mismo criterio no negociable que NMAP_AUTHORIZED_TARGETS: el USUARIO
    # edita este archivo a mano, ninguna tool ni el LLM puede escribirlo. Un
    # target en la lista NO necesita estar corriendo/alcanzable en este
    # momento para estar "autorizado" -- los labs (PyGoat/NodeGoat/etc.) se
    # levantan bajo demanda, así que la autorización es independiente de que
    # el target esté vivo ahora mismo (eso lo valida cada tool al ejecutar,
    # nunca el gate). NMAP_AUTHORIZED_TARGETS de arriba se sigue leyendo
    # además de este archivo, por retrocompatibilidad -- no se rompe una
    # config que ya tenías andando.
    authorized_targets_path: str = os.getenv(
        "AUTHORIZED_TARGETS_PATH", str(Path(__file__).resolve().parent.parent / "authorized_targets.yaml")
    )

    # sqlmap_scan (ver app/tools/pentest_sqlmap.py + app/pentest/) -- primera
    # tool de pentesting ACTIVO del proyecto (a diferencia de nmap_scan, que
    # es reconocimiento pasivo: puertos/servicios, nunca envía payloads de
    # ataque). Gateada por el mismo guardrail no negociable de
    # authorized_targets.yaml, aplicado sobre el HOST de la URL antes de
    # correr nada. sqlmap es pura Python (sin UAC/admin, a diferencia de
    # nmap/Npcap) -- instalación manual: 'git clone --depth 1
    # https://github.com/sqlmapproject/sqlmap.git' y apuntar SQLMAP_PATH al
    # sqlmap.py resultante.
    sqlmap_enabled: bool = _bool(os.getenv("SQLMAP_ENABLED"), True)
    sqlmap_path: str = os.getenv("SQLMAP_PATH", str(Path.home() / "sqlmap-dev" / "sqlmap.py"))
    # REST API de SQLMap (sqlmapapi.py) -- SOLO localhost, nunca expuesta a
    # la red; Jarvis la arranca sola (lazy, si no está corriendo ya) cuando
    # hace falta. Credenciales HTTP Basic generadas una vez y persistidas
    # (ver app/pentest/sqlmap_client.py::_load_or_create_credentials) --
    # no hace falta configurarlas a mano.
    sqlmap_api_host: str = os.getenv("SQLMAP_API_HOST", "127.0.0.1")
    sqlmap_api_port: int = int(os.getenv("SQLMAP_API_PORT", "8775"))
    sqlmap_api_credentials_path: str = os.getenv(
        "SQLMAP_API_CREDENTIALS_PATH", str(Path(__file__).resolve().parent.parent / "sqlmap_api_credentials.json")
    )

    # packet_capture_scan / packet_capture_analyze (ver app/pentest/
    # packet_capture.py, "Wireshark" en la spec de Damian) -- implementado con
    # `scapy` (pip, sin binario externo) en vez de shellear a tshark.exe,
    # decisión documentada en el docstring del módulo. La mitad "analizar un
    # .pcap ya existente" no necesita Npcap ni nada más; la mitad "capturar en
    # vivo" sí (mismo click de UAC que nmap, ver https://npcap.com/#download).
    # Gateada distinto del resto: no hay un "target" remoto único, hay una
    # interfaz LOCAL -- exige host_filter no vacío, cada host pasa por el
    # mismo authorized_targets.yaml compartido (nunca captura sin acotar).
    packet_capture_enabled: bool = _bool(os.getenv("PACKET_CAPTURE_ENABLED"), True)
    pcap_output_dir: str = os.getenv(
        "PCAP_OUTPUT_DIR", str(Path(__file__).resolve().parent.parent.parent / "content" / "captures")
    )

    # zap_scan (ver app/tools/pentest_zap.py + app/pentest/zap_client.py,
    # checkpoint 5 -- OWASP ZAP en vez de Burp Suite Pro, decisión de Damian
    # 2026-08-13: ZAP es gratis y tiene REST API completa, Burp Pro necesita
    # licencia paga que no tiene). Gateado por el mismo guardrail no
    # negociable de authorized_targets.yaml, sobre el HOST de la URL, igual
    # que sqlmap_scan. ZAP se distribuye "Crossplatform" (zip, sin
    # instalador/UAC -- necesita Java 11+, ya presente en esta máquina) --
    # instalación manual: descargar el zip "Crossplatform" desde
    # https://github.com/zaproxy/zaproxy/releases/latest y apuntar ZAP_PATH
    # al zap-X.Y.Z.jar resultante.
    zap_enabled: bool = _bool(os.getenv("ZAP_ENABLED"), True)
    zap_path: str = os.getenv("ZAP_PATH", str(Path.home() / "zap-2.17.0" / "zap-2.17.0.jar"))
    # Daemon REST API de ZAP -- SOLO localhost, arrancado lazy por Jarvis
    # (mismo criterio que sqlmapapi.py). API key generada una vez y
    # persistida (ver app/pentest/zap_client.py::_load_or_create_api_key).
    zap_api_host: str = os.getenv("ZAP_API_HOST", "127.0.0.1")
    zap_api_port: int = int(os.getenv("ZAP_API_PORT", "8090"))
    zap_api_key_path: str = os.getenv(
        "ZAP_API_KEY_PATH", str(Path(__file__).resolve().parent.parent / "zap_api_key.json")
    )

    # opencode_run_task (ver app/tools/opencode.py, agregado 2026-08-11) --
    # delega tareas pesadas de escritura/edición de código a la CLI de
    # OpenCode (github.com/sst/opencode, MIT), apuntada al mismo Ollama local
    # que ya sirve jarvis-text-v2 (ver provider "jarvis-ollama" en
    # ~/.config/opencode/opencode.json) en vez de al propio loop de agente de
    # Jarvis. Mismo binario para todas las instalaciones por default (instalado
    # vía `curl -fsSL https://opencode.ai/install | bash`, que en Windows deja
    # el .exe en %USERPROFILE%\.opencode\bin) -- configurable por si en otra
    # máquina quedó en otro lado.
    opencode_bin_path: str = os.getenv(
        "OPENCODE_BIN_PATH", str(Path.home() / ".opencode" / "bin" / "opencode.exe")
    )
    opencode_default_model: str = os.getenv("OPENCODE_DEFAULT_MODEL", "jarvis-ollama/jarvis-text-v2")

    # cloud_expert_code/cloud_expert_marketing (ver app/tools/cloud_expert.py,
    # agregado 2026-08-12) -- delegan a Gemini Flash (API gratuita de Google
    # AI Studio, ~15 req/min y 1M tokens/día en el free tier, sin tarjeta) un
    # primer borrador de código o de texto de marketing. Reusa el SDK de
    # OpenAI (mismo patrón que llm_client.py) apuntado al endpoint
    # OpenAI-compatible real de Gemini (generativelanguage.googleapis.com/
    # v1beta/openai/), en vez de escribir un cliente REST propio -- Google
    # publica esta compatibilidad justamente para no tener que reimplementar
    # el cliente por proveedor. Vacío por default a propósito: sin
    # GOOGLE_AI_API_KEY seteada en backend/.env, ambas tools fallan con un
    # error claro en vez de intentar una llamada que va a rechazar la API.
    google_ai_api_key: str = os.getenv("GOOGLE_AI_API_KEY", "")
    google_ai_base_url: str = os.getenv(
        "GOOGLE_AI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    google_ai_model: str = os.getenv("GOOGLE_AI_MODEL", "gemini-2.5-flash")

    # Perfil de investigación científica (ver app/obsidian/profile.py +
    # app/agent.py, agregado 2026-08-12) -- vault y directorio de trabajo
    # SEPARADOS del vault/codebase de seguridad de JarvisRemote, para que
    # Damian pueda usar a Jarvis como asistente de su propia investigación
    # de biotecnología sin mezclar esas notas con las de auditoría de
    # código. Mismo backend/modelo que el perfil default -- no es una
    # segunda instancia corriendo en paralelo (12GB de VRAM no da para dos
    # modelos grandes a la vez), es un cambio de contexto dentro de la
    # misma conversación/proceso.
    research_vault_path: str = os.getenv(
        "RESEARCH_VAULT_PATH", str(Path(__file__).resolve().parent.parent / "obsidian_vault_investigacion")
    )
    research_embeddings_path: str = os.getenv(
        "RESEARCH_EMBEDDINGS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "research_embeddings.json")
    )
    research_working_dir: str = os.getenv(
        "RESEARCH_WORKING_DIR", str(Path.home() / "Documents" / "Investigacion")
    )

    # Módulo de investigación (análisis de enlaces y evidencia digital, ver
    # app/investigation/ -- spec de Damian, 2026-08-12). Tres directorios
    # separados a propósito, mismo criterio que el resto del proyecto
    # (nunca mezclar cache/datos derivados con el vault/repo real):
    # - investigation_cases_dir: un subdirectorio por caso, CADA UNO su
    #   propio repo git (versiona grafo/log/metadata -- nunca los binarios).
    # - investigation_artifact_store_dir: almacén único, compartido entre
    #   TODOS los casos, de solo lectura, indexado por sha256 -- NUNCA
    #   versionado con git (decisión explícita de Damian: los binarios
    #   originales no van a git).
    # - investigation_keys_dir: clave de firma Ed25519 del log append-only
    #   (ver app/investigation/keys.py), protegida con DPAPI -- vive fuera
    #   de cualquier directorio versionado o exportable por accidente.
    investigation_cases_dir: str = os.getenv(
        "INVESTIGATION_CASES_DIR", str(Path(__file__).resolve().parent.parent / "investigation_cases")
    )
    investigation_artifact_store_dir: str = os.getenv(
        "INVESTIGATION_ARTIFACT_STORE_DIR",
        str(Path(__file__).resolve().parent.parent / "data" / "investigation_artifacts"),
    )
    investigation_keys_dir: str = os.getenv(
        "INVESTIGATION_KEYS_DIR", str(Path(__file__).resolve().parent.parent / "data" / "investigation_keys")
    )

    # Módulo de protección contra malware (ver app/malware/ -- spec de
    # Damian, 2026-08-16). Motor: YARA (reglas de firmas + heurística propia)
    # + ClamAV (clamd, firmas masivas) + capa conductual (watchdog/psutil)
    # desde el arranque, ninguno como fase 2. Reusa el MISMO artifact_store
    # de app/investigation/ (INVESTIGATION_ARTIFACT_STORE_DIR de arriba, no
    # una copia separada) y el mismo mecanismo de firma Ed25519
    # (investigation/keys.py, mismo INVESTIGATION_KEYS_DIR) para su propio
    # log append-only -- decisión de diseño C de la ronda de preguntas: un
    # hallazgo de malware queda igual de trazable/verificable que un caso de
    # investigación, sin forzarlo dentro del modelo de "caso" (que es sobre
    # personas/timelines, un dominio distinto).
    malware_log_path: str = os.getenv(
        "MALWARE_LOG_PATH", str(Path(__file__).resolve().parent.parent / "data" / "malware_log.jsonl")
    )

    # Carpeta donde se mueven los archivos sospechosos en cuarentena (fuera de
    # cualquier ruta ejecutable/de inicio automático) -- reversible por
    # default (mover, no borrar, decisión de la pregunta 3: cuarentena por
    # default, eliminación definitiva solo con confirm=true explícito, mismo
    # patrón dry-run->confirm=true que code_apply_fix).
    malware_quarantine_dir: str = os.getenv(
        "MALWARE_QUARANTINE_DIR", str(Path(__file__).resolve().parent.parent / "data" / "malware_quarantine")
    )

    # Reglas YARA -- directorio con archivos .yar/.yara, cargados todos al
    # compilar. Viene con un set inicial propio (ver
    # app/malware/rules/starter.yar) mas lo que Damian agregue a mano (ej.
    # reglas descargadas de github.com/Yara-Rules/rules o similares).
    malware_yara_rules_dir: str = os.getenv(
        "MALWARE_YARA_RULES_DIR", str(Path(__file__).resolve().parent.parent / "app" / "malware" / "rules")
    )

    # FIM (File Integrity Monitoring, auto-protección parte A) -- manifiesto
    # baseline (hash SHA-256 por archivo vigilado) y lista de archivos/carpetas
    # críticos de la propia instalación de Jarvis. Coma-separado, rutas
    # absolutas o relativas a backend/. Default: el gate de pentesting
    # (authorized_targets.yaml), las claves de firma del módulo de
    # investigación (que ahora también firman el log de malware), el .env con
    # credenciales en texto plano, y el código fuente de app/ entero (para
    # detectar una modificación no versionada -- ej. inyectada por un proceso
    # malicioso -- antes del próximo `git status`).
    malware_integrity_baseline_path: str = os.getenv(
        "MALWARE_INTEGRITY_BASELINE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "malware_integrity_baseline.json")
    )
    malware_integrity_watch_paths: str = os.getenv(
        "MALWARE_INTEGRITY_WATCH_PATHS",
        ",".join([
            str(Path(__file__).resolve().parent.parent / "authorized_targets.yaml"),
            str(Path(__file__).resolve().parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent / "data" / "investigation_keys"),
            str(Path(__file__).resolve().parent.parent / "app"),
        ]),
    )

    # Vigilancia del proceso propio (auto-protección parte B, ver
    # app/malware/process_monitor.py) -- procesos hijos inesperados del PID
    # del backend y conexiones salientes fuera de lo esperado (LM Studio/
    # Ollama local, ClamAV local, VirusTotal, Tailscale). Prendida por
    # default (mismo criterio que el resto de las tools "sin fricción" del
    # proyecto), con flag real para apagarla.
    malware_process_monitor_enabled: bool = _bool(os.getenv("MALWARE_PROCESS_MONITOR_ENABLED"), True)

    # ClamAV real vía el daemon `clamd` -- requiere instalación manual (ver
    # backend/README.md, sección malware) + el servicio `clamd` corriendo en
    # esta IP/puerto. Sin eso, malware_scan_path sigue funcionando con YARA +
    # heurística conductual, solo se salta ClamAV con un aviso explícito (no
    # falla el escaneo entero por una pieza optativa no instalada).
    clamd_host: str = os.getenv("CLAMD_HOST", "127.0.0.1")
    clamd_port: int = int(os.getenv("CLAMD_PORT", "3310"))
    clamav_enabled: bool = _bool(os.getenv("CLAMAV_ENABLED"), True)

    # VirusTotal -- SOLO confirmación selectiva de hashes ya marcados
    # sospechosos localmente (decisión de la pregunta 5), nunca sube contenido
    # de archivos. Vacío por default: sin VIRUSTOTAL_API_KEY, esa capa se
    # salta con un aviso explícito (mismo criterio que GOOGLE_AI_API_KEY).
    # Sacar una key gratis en https://www.virustotal.com/gui/join-us.
    virustotal_api_key: str = os.getenv("VIRUSTOTAL_API_KEY", "")
    virustotal_cache_path: str = os.getenv(
        "VIRUSTOTAL_CACHE_PATH", str(Path(__file__).resolve().parent.parent / "data" / "virustotal_cache.json")
    )
    # Límite real del tier gratis: 4 req/min. Se deja margen (15s entre
    # consultas = 4/min exacto) para no comerse baneos temporales por ráfagas.
    virustotal_min_seconds_between_requests: float = float(os.getenv("VIRUSTOTAL_MIN_SECONDS_BETWEEN_REQUESTS", "15"))

    # Sysmon (Sysinternals/Microsoft, driver YA firmado -- no es un driver
    # propio) -- capa EXPERIMENTAL de auto-protección parte C (detección tipo
    # EDR real: acceso a memoria del propio proceso, hijos remotos, etc.).
    # Instalación manual (ver backend/README.md). Apagada por default a
    # propósito: a diferencia del resto de este módulo (A+B, sólidos), C se
    # documentó explícitamente como experimental -- Damian eligió sumarla
    # igual sabiendo que la señal puede ser ruidosa/no confiable, así que
    # arranca en false hasta que la instale y la prenda a mano.
    sysmon_enabled: bool = _bool(os.getenv("SYSMON_ENABLED"), False)
    sysmon_event_log_channel: str = os.getenv("SYSMON_EVENT_LOG_CHANNEL", "Microsoft-Windows-Sysmon/Operational")

    # Escaneo completo del árbol bajo FS_ALLOWED_ROOT, corrido una vez cada 24h
    # (decisión de la pregunta 2: escaneo diario, no semanal) por un loop en
    # background arrancado en el startup del backend (ver app/main.py) --
    # ninguna configuración de Task Scheduler de Windows necesaria aparte.
    # Ojo: NO es "todo el disco C:\" literal (Windows/Program Files incluidos
    # sería enormemente más lento y en su mayoría archivos del sistema que
    # Windows Defender ya cubre) -- es el árbol completo de FS_ALLOWED_ROOT
    # (la carpeta de usuario), que es lo que en la práctica contiene los
    # archivos que el propio Damian descarga/crea/recibe. Configurable si
    # de verdad se quiere escanear otra raíz.
    malware_full_scan_enabled: bool = _bool(os.getenv("MALWARE_FULL_SCAN_ENABLED"), True)
    malware_full_scan_interval_hours: float = float(os.getenv("MALWARE_FULL_SCAN_INTERVAL_HOURS", "24"))
    malware_full_scan_root: str = os.getenv("MALWARE_FULL_SCAN_ROOT", "")  # vacío = usa fs_allowed_root

    # Carpetas de riesgo típico para el escaneo "on-access" (YARA+ClamAV sobre
    # cada archivo nuevo apenas aparece, vía watchdog) -- coma-separado.
    # Default: Descargas/Escritorio/Temp del usuario actual.
    malware_watch_folders: str = os.getenv(
        "MALWARE_WATCH_FOLDERS",
        ",".join([
            str(Path.home() / "Downloads"),
            str(Path.home() / "Desktop"),
            os.getenv("TEMP", str(Path.home() / "AppData" / "Local" / "Temp")),
        ]),
    )

    # Credenciales generadas por Jarvis al completar formularios/registros web
    # (ver app/tools/web_forms.py + app/forms/credential_store.py) -- cifradas
    # con DPAPI, mismo mecanismo que investigation_keys_dir de arriba (ver ese
    # módulo para el razonamiento completo). Decisión de la ronda de
    # preguntas de "formularios web" 2026-08-16: Damian pidió guardarlas en
    # un archivo (no solo mostrarlas una vez en el chat) -- texto plano fue
    # descartado a propósito, mismo antipatrón ya señalado sobre .env.
    form_credentials_path: str = os.getenv(
        "FORM_CREDENTIALS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "form_credentials.dpapi")
    )

    # Capturas de pantalla del dry-run de browser_preview_submit (ver
    # app/tools/web_forms.py) -- previsualización real de qué se va a enviar
    # ANTES de tocar el botón de submit, pedido explícito de Damian (sin
    # excepción, ni para formularios simples de un par de campos).
    form_preview_dir: str = os.getenv(
        "FORM_PREVIEW_DIR", str(Path(__file__).resolve().parent.parent / "data" / "form_previews")
    )

    # Grabación de pantalla real (ffmpeg, ver app/recording.py) -- se activa
    # sola alrededor de cualquier tool de la familia auditoría/fix/test (ver
    # app/tools/__init__.py::_RECORDABLE_TOOL_NAMES) para documentar el
    # trabajo de Jarvis de punta a punta con contenido real, pedido explícito
    # de Damian 2026-08-13. Tan sensible en privacidad como
    # DESKTOP_CONTROL_ENABLED (graba TODO el escritorio, no solo la ventana
    # relevante -- cualquier otra cosa visible en pantalla en ese momento
    # queda en el video) -- prendida por default porque ESE es el punto de la
    # feature (capturar sin que Damian tenga que acordarse de arrancarla a
    # mano cada vez), pero con un apagador real y efectivo por si en algún
    # momento hay algo en pantalla que no debería quedar grabado.
    screen_recording_enabled: bool = _bool(os.getenv("SCREEN_RECORDING_ENABLED"), True)

    # Carpeta de salida de las grabaciones -- a propósito en la RAÍZ del repo
    # (content/recordings/, hermana de backend/, no adentro de backend/):
    # esto es contenido humano/de publicación (mismo criterio que
    # Fundamentos_de_Jarvis.docx, que también vive en la raíz), no un dato
    # operativo del backend como investigation_cases_dir o selfrepair_dir.
    recording_output_dir: str = os.getenv(
        "RECORDING_OUTPUT_DIR", str(Path(__file__).resolve().parent.parent.parent / "content" / "recordings")
    )


settings = Settings()

if settings._api_key_was_generated:
    print(
        "[jarvis-backend] No API_KEY set in .env — generated one for this run:\n"
        f"  {settings.api_key}\n"
        "  Set API_KEY in backend/.env to keep it stable across restarts."
    )
