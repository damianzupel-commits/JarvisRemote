# 15 · Configuración: todas las variables de entorno

Todo viene de `app/config.py` (clase `Settings`, instancia global `settings`), leído del `backend/.env`
vía `python-dotonv`. Helpers: `_bool(value, default)` (acepta `1/true/yes/on`), `_split_paths(value)`
(separa por coma/`;`, nunca por `:` para no partir rutas de Windows). `_PROJECT_ROOT` = raíz del repo.
Si `API_KEY` no está seteada, se genera una por arranque y se imprime.

## Servidor y API
| Variable | Default | Qué hace |
|----------|---------|----------|
| `HOST` | `0.0.0.0` | bind del server |
| `PORT` | `8000` | puerto |
| `API_KEY` | *(generada)* | Bearer token de `/api/chat` y `/ws/phone` |

## LLM de chat/agente
| Variable | Default | Qué hace |
|----------|---------|----------|
| `LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` | endpoint OpenAI-compatible del LLM (hoy apunta a Ollama :11434 en la PC real) |
| `LMSTUDIO_MODEL` | `local-model` | modelo de chat (real: `gpt-oss:120b-cloud` o `jarvis-text-v2`) |
| `LLM_API_KEY` | `lm-studio` | key del proveedor (local no valida; cloud sí) |
| `LLM_REQUEST_TIMEOUT_SECONDS` | `1800` | timeout de la llamada (generoso: no cortar generaciones lentas) |
| `LLM_RETRY_MAX_ATTEMPTS` | `3` | reintentos ante error transitorio de red |
| `LLM_RETRY_BASE_DELAY_SECONDS` | `1.0` | backoff base |
| `LLM_RETRY_MAX_DELAY_SECONDS` | `30.0` | backoff máximo |
| `LLM_RETRY_ON_TIMEOUT` | `false` | reintentar ante timeout (solo tiene sentido con modelo cloud) |

## Embeddings
| Variable | Default | Qué hace |
|----------|---------|----------|
| `EMBEDDING_BASE_URL` | `http://127.0.0.1:1234/v1` | server de embeddings (LM Studio real, separado del chat) |
| `EMBEDDING_MODEL` | `text-embedding-nomic-embed-text-v1.5` | modelo de embeddings del vault |

## Sandbox de filesystem y modos de operación
| Variable | Default | Qué hace |
|----------|---------|----------|
| `FS_ALLOWED_ROOT` | *(raíz del proyecto)* | raíz principal del sandbox acotado (AUTÓNOMO) |
| `FS_ALLOWED_ROOTS` | *(vacío)* | raíces extra (coma-separadas) que se suman a la anterior |
| `FS_ALLOW_DELETE` | `false` | habilita `fs_delete_path` |
| `FS_SUPERVISED_ROOT` | *(HOME)* | raíz amplia del modo SUPERVISADO |
| `JARVIS_OPERATION_MODE` | *(vacío→AUTÓNOMO)* | default del proceso (`supervised`/`autonomous`); fail-safe a AUTÓNOMO |

## Presupuesto de contexto e iteraciones
| Variable | Default | Qué hace |
|----------|---------|----------|
| `MAX_AGENT_ITERATIONS` | `10` | tope de pasos del loop (chat/auditoría) |
| `MAX_AGENT_ITERATIONS_CODE_TASK` | `50` | tope extendido tras el primer `fs_write_file` |
| `MAX_HISTORY_MESSAGES` | `40` | poda por cantidad de mensajes |
| `MAX_TOOL_RESULT_CHARS` | `6000` | tope de tamaño de un solo tool result |
| `MODEL_CONTEXT_TOKENS` | `32768` | contexto real del modelo (sincronizar con `num_ctx`) |
| `RESERVED_RESPONSE_TOKENS` | `3000` | tokens reservados para la respuesta (= `max_tokens`) |
| `CHARS_PER_TOKEN_ESTIMATE` | `3.2` | proxy chars/token (conservador) |

## Control de PC / navegador
| Variable | Default | Qué hace |
|----------|---------|----------|
| `BROWSER_HEADLESS` | `false` | navegador con o sin ventana |
| `DESKTOP_CONTROL_ENABLED` | `true` | habilita mouse/teclado/ventanas |
| `PC_SHELL_ENABLED` | `true` | habilita `pc_run_command` |

## Celular / cámara / video
| Variable | Default | Qué hace |
|----------|---------|----------|
| `PHONE_TOOL_TIMEOUT` | `30` | espera de respuesta del celular por WS |
| `PHONE_SHELL_ENABLED` | `true` | habilita `phone_run_command` (Termux) |
| `PHONE_CAMERA_ENABLED` | `true` | habilita foto/video del celular |
| `VIDEO_FRAME_INTERVAL_SECONDS` | `1.5` | intervalo de extracción de frames |
| `VIDEO_MAX_FRAMES` | `8` | máximo de frames por video |

## TLS
| Variable | Default | Qué hace |
|----------|---------|----------|
| `TLS_ENABLED` | `false` | servir wss/https (apagado a propósito) |
| `TLS_CERT_PATH` | `backend/certs/cert.pem` | cert |
| `TLS_KEY_PATH` | `backend/certs/key.pem` | key |

## Vault, reflexión, caches derivados
| Variable | Default | Qué hace |
|----------|---------|----------|
| `REFLECTIONS_PATH` | `backend/reflections.jsonl` | memoria de `jarvis_reflect` |
| `OBSIDIAN_VAULT_PATH` | `backend/obsidian_vault` | vault de conocimiento |
| `OBSIDIAN_EMBEDDINGS_PATH` | `backend/data/obsidian_embeddings.json` | índice de embeddings |
| `CODEBASE_INDEX_DIR` | `backend/data/codebase_index` | cache de índices de código |
| `SECURITY_SCAN_DIR` | `backend/data/security_scans` | cache de escaneos de seguridad |
| `QUALITY_SCAN_DIR` | `backend/data/quality_scans` | cache de escaneos de calidad |
| `TEST_RUN_DIR` | `backend/data/test_runs` | cache de la última corrida de tests |
| `SELFREPAIR_DIR` | `backend/data/selfrepair` | store de propuestas de self-repair |

## ComfyUI (generación de imagen/video — tools DESACTIVADAS)
| Variable | Default | Qué hace |
|----------|---------|----------|
| `COMFYUI_DIR` | `E:\ComfyUI\ComfyUI_windows_portable` | instalación portable |
| `COMFYUI_BASE_URL` | `http://127.0.0.1:8188` | API HTTP de ComfyUI |
| `COMFYUI_STARTUP_TIMEOUT` | `240` | timeout de arranque |
| `COMFYUI_PYTHON_PATH` | `…\env_rocm\Scripts\python.exe` | venv ROCm que no crashea en esta GPU |
| `COMFYUI_GENERATION_TIMEOUT_IMAGE` | `600` | timeout de generación de imagen |
| `OLLAMA_NATIVE_BASE_URL` | `http://127.0.0.1:11434` | API nativa de Ollama (descargar/recargar el modelo de la VRAM) |

> Estas tools están **comentadas en el registro** (no importadas) por precaución de hardware. Ver [03](03-tools-registro-catalogo.md).

## Pentesting: nmap, sqlmap, ZAP, captura
| Variable | Default | Qué hace |
|----------|---------|----------|
| `NMAP_ENABLED` | `true` | habilita `nmap_scan` |
| `NMAP_AUTHORIZED_TARGETS` | *(vacío)* | whitelist retrocompatible de IPs/CIDR públicos |
| `AUTHORIZED_TARGETS_PATH` | `backend/authorized_targets.yaml` | **fuente única** de autorización de pentesting |
| `SQLMAP_ENABLED` | `true` | habilita `sqlmap_scan` |
| `SQLMAP_PATH` | `~/sqlmap-dev/sqlmap.py` | ruta al sqlmap.py |
| `SQLMAP_API_HOST` / `SQLMAP_API_PORT` | `127.0.0.1` / `8775` | REST API (solo localhost) |
| `SQLMAP_API_CREDENTIALS_PATH` | `backend/sqlmap_api_credentials.json` | credenciales HTTP Basic (autogeneradas) |
| `PACKET_CAPTURE_ENABLED` | `true` | habilita captura de paquetes (scapy) |
| `PCAP_OUTPUT_DIR` | `content/captures` | salida de `.pcap` |
| `ZAP_ENABLED` | `true` | habilita `zap_scan` |
| `ZAP_PATH` | `~/zap-2.17.0/zap-2.17.0.jar` | ruta al .jar de ZAP |
| `ZAP_API_HOST` / `ZAP_API_PORT` | `127.0.0.1` / `8090` | daemon REST (solo localhost) |
| `ZAP_API_KEY_PATH` | `backend/zap_api_key.json` | API key de ZAP (autogenerada) |

## Delegación de código / cloud
| Variable | Default | Qué hace |
|----------|---------|----------|
| `OPENCODE_BIN_PATH` | `~/.opencode/bin/opencode.exe` | binario de OpenCode |
| `OPENCODE_DEFAULT_MODEL` | `jarvis-ollama/jarvis-text-v2` | modelo que usa OpenCode (Ollama local) |
| `GOOGLE_AI_API_KEY` | *(vacío)* | key de Gemini Flash (sin ella, `cloud_expert_*` fallan) |
| `GOOGLE_AI_BASE_URL` | `…/v1beta/openai/` | endpoint OpenAI-compatible de Gemini |
| `GOOGLE_AI_MODEL` | `gemini-2.5-flash` | modelo cloud puntual |

## Perfil de investigación científica
| Variable | Default | Qué hace |
|----------|---------|----------|
| `RESEARCH_VAULT_PATH` | `backend/obsidian_vault_investigacion` | vault separado |
| `RESEARCH_EMBEDDINGS_PATH` | `backend/data/research_embeddings.json` | índice separado |
| `RESEARCH_WORKING_DIR` | `~/Documents/Investigacion` | directorio de trabajo del perfil research |

## Módulo de investigación forense
| Variable | Default | Qué hace |
|----------|---------|----------|
| `INVESTIGATION_CASES_DIR` | `backend/investigation_cases` | un subdirectorio/repo git por caso |
| `INVESTIGATION_ARTIFACT_STORE_DIR` | `backend/data/investigation_artifacts` | almacén por sha256 (nunca a git) |
| `INVESTIGATION_KEYS_DIR` | `backend/data/investigation_keys` | clave Ed25519 (DPAPI) del log firmado |

## Malware / defensa
| Variable | Default | Qué hace |
|----------|---------|----------|
| `MALWARE_LOG_PATH` | `backend/data/malware_log.jsonl` | log firmado de hallazgos |
| `MALWARE_QUARANTINE_DIR` | `backend/data/malware_quarantine` | cuarentena reversible |
| `MALWARE_YARA_RULES_DIR` | `backend/app/malware/rules` | reglas YARA |
| `MALWARE_INTEGRITY_BASELINE_PATH` | `backend/data/malware_integrity_baseline.json` | baseline FIM |
| `MALWARE_INTEGRITY_WATCH_PATHS` | *(authorized_targets, .env, keys, app/)* | archivos críticos vigilados |
| `MALWARE_PROCESS_MONITOR_ENABLED` | `true` | vigilancia del proceso propio |
| `CLAMD_HOST` / `CLAMD_PORT` | `127.0.0.1` / `3310` | daemon ClamAV |
| `CLAMAV_ENABLED` | `true` | habilita ClamAV (se salta con aviso si no está) |
| `VIRUSTOTAL_API_KEY` | *(vacío)* | confirmación selectiva de hashes |
| `VIRUSTOTAL_CACHE_PATH` | `backend/data/virustotal_cache.json` | cache |
| `VIRUSTOTAL_MIN_SECONDS_BETWEEN_REQUESTS` | `15` | rate limit del free tier |
| `SYSMON_ENABLED` | `false` | capa EDR experimental (apagada) |
| `SYSMON_EVENT_LOG_CHANNEL` | `Microsoft-Windows-Sysmon/Operational` | canal del Event Log |
| `MALWARE_FULL_SCAN_ENABLED` | `true` | escaneo completo diario |
| `MALWARE_FULL_SCAN_INTERVAL_HOURS` | `24` | intervalo del escaneo completo |
| `MALWARE_FULL_SCAN_ROOT` | *(vacío→HOME)* | raíz del barrido completo |
| `MALWARE_WATCH_FOLDERS` | *(Downloads/Desktop/Temp)* | carpetas de escaneo on-access |

## Formularios web y credenciales
| Variable | Default | Qué hace |
|----------|---------|----------|
| `FORM_CREDENTIALS_PATH` | `backend/data/form_credentials.dpapi` | store cifrado DPAPI |
| `FORM_PREVIEW_DIR` | `backend/data/form_previews` | capturas del dry-run de submit |
| `FORM_PREVIEW_TOKEN_TTL_SECONDS` | `300` | TTL del preview_token de un solo uso |

## Grabación de pantalla
| Variable | Default | Qué hace |
|----------|---------|----------|
| `SCREEN_RECORDING_ENABLED` | `true` | grabación automática (ffmpeg) del pipeline |
| `RECORDING_OUTPUT_DIR` | `content/recordings` | salida de los `.mp4` (gitignoreado) |
