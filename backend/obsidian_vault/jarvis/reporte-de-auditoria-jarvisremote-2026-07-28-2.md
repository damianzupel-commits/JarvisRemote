---
author: jarvis
created: '2026-07-28T21:20:26.222459+00:00'
tags:
- reportes
- auditoria
- seguridad
- calidad
title: Reporte de auditoría -- JarvisRemote -- 2026-07-28
updated: '2026-07-28T21:20:26.222459+00:00'
---

# Reporte de auditoría de código -- JarvisRemote

- Proyecto: `C:\Users\dam\Documents\JarvisRemote`
- Generado: 2026-07-28T21:20:26.221460+00:00
- Último escaneo de seguridad: 2026-07-28T18:42:02.314630+00:00 (corrieron: semgrep, bandit)
- Último escaneo de calidad: 2026-07-28T21:17:08.943590+00:00 (corrieron: ruff, mypy)

## Resumen ejecutivo

577 hallazgo(s) de seguridad (0 crítico(s), 6 alto(s)). 61 hallazgo(s) de calidad (38 alto(s)). 0 fix(es) y 1 edición(es) general(es) ya aplicados, todos revertibles con git revert.

## Hallazgos de seguridad (577)

| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |
|---|---|---|---|---|
| high | `android-app/app/src/main/java/com/jarvisremote/app/phone/PhoneLinkService.kt` | 187 | `javascript.lang.security.detect-insecure-websocket.detect-insecure-websocket` (semgrep) | Insecure WebSocket Detected. WebSocket Secure (wss) should be used for all WebSocket connections. |
| high | `backend/.env.example` | 68 | `javascript.lang.security.detect-insecure-websocket.detect-insecure-websocket` (semgrep) | Insecure WebSocket Detected. WebSocket Secure (wss) should be used for all WebSocket connections. |
| high | `backend/README.md` | 284 | `javascript.lang.security.detect-insecure-websocket.detect-insecure-websocket` (semgrep) | Insecure WebSocket Detected. WebSocket Secure (wss) should be used for all WebSocket connections. |
| high | `backend/app/config.py` | 71 | `javascript.lang.security.detect-insecure-websocket.detect-insecure-websocket` (semgrep) | Insecure WebSocket Detected. WebSocket Secure (wss) should be used for all WebSocket connections. |
| high | `backend/certs/README.md` | 5 | `javascript.lang.security.detect-insecure-websocket.detect-insecure-websocket` (semgrep) | Insecure WebSocket Detected. WebSocket Secure (wss) should be used for all WebSocket connections. |
| high | `backend/certs/README.md` | 9 | `javascript.lang.security.detect-insecure-websocket.detect-insecure-websocket` (semgrep) | Insecure WebSocket Detected. WebSocket Secure (wss) should be used for all WebSocket connections. |
| medium | `android-app/app/src/main/AndroidManifest.xml` | 75 | `java.android.security.exported_activity.exported_activity` (semgrep) | The application exports an activity. Any application on the device can launch the exported activity which may compromise the integrity of your application or it |
| medium | `backend/app/config.py` | 17 | `B104` (bandit) | Possible binding to all interfaces. |
| medium | `tray-app/config.py` | 18 | `B104` (bandit) | Possible binding to all interfaces. |
| medium | `tray-app/tests/test_codebase_view.py` | 67 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 198 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 260 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 267 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 278 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 291 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 314 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 326 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 354 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 360 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/tests/test_codebase_view.py` | 363 | `B108` (bandit) | Probable insecure usage of temp file/directory. |
| medium | `tray-app/ui/web_assets/graph3d.html` | 15 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| low | `android-app/app/src/main/java/com/jarvisremote/app/data/ApiKeyCrypto.kt` | 65 | `kotlin.lang.security.gcm-detection.gcm-detection` (semgrep) | GCM detected, please check that IV/nonce is not reused, an Initialization Vector (IV) is a nonce used to randomize the encryption, so that even if multiple mess |
| low | `android-app/app/src/main/java/com/jarvisremote/app/data/ApiKeyCrypto.kt` | 79 | `kotlin.lang.security.gcm-detection.gcm-detection` (semgrep) | GCM detected, please check that IV/nonce is not reused, an Initialization Vector (IV) is a nonce used to randomize the encryption, so that even if multiple mess |
| low | `android-app/app/src/main/java/com/jarvisremote/app/data/ApiKeyCrypto.kt` | 80 | `kotlin.lang.security.gcm-detection.gcm-detection` (semgrep) | GCM detected, please check that IV/nonce is not reused, an Initialization Vector (IV) is a nonce used to randomize the encryption, so that even if multiple mess |
| low | `backend/app/security/fixer.py` | 23 | `B404` (bandit) | Consider possible security implications associated with the subprocess module. |
| low | `backend/app/security/fixer.py` | 45 | `B607` (bandit) | Starting a process with a partial executable path |
| low | `backend/app/security/fixer.py` | 45 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/security/fixer.py` | 60 | `B607` (bandit) | Starting a process with a partial executable path |
| low | `backend/app/security/fixer.py` | 60 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/security/fixer.py` | 68 | `B607` (bandit) | Starting a process with a partial executable path |
| low | `backend/app/security/fixer.py` | 68 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/security/scanners.py` | 18 | `B404` (bandit) | Consider possible security implications associated with the subprocess module. |
| low | `backend/app/security/scanners.py` | 73 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/security/scanners.py` | 133 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/security/scanners.py` | 184 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/tools/_comfyui_shared.py` | 8 | `B404` (bandit) | Consider possible security implications associated with the subprocess module. |
| low | `backend/app/tools/_comfyui_shared.py` | 77 | `B607` (bandit) | Starting a process with a partial executable path |
| low | `backend/app/tools/_comfyui_shared.py` | 77 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/tools/_comfyui_shared.py` | 91 | `B607` (bandit) | Starting a process with a partial executable path |
| low | `backend/app/tools/_comfyui_shared.py` | 91 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/tools/_comfyui_shared.py` | 107 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/tools/desktop.py` | 38 | `B404` (bandit) | Consider possible security implications associated with the subprocess module. |
| low | `backend/app/tools/desktop.py` | 252 | `B112` (bandit) | Try, Except, Continue detected. |
| low | `backend/app/tools/desktop.py` | 563 | `B606` (bandit) | Starting a process without a shell. |
| low | `backend/app/tools/desktop.py` | 570 | `B607` (bandit) | Starting a process with a partial executable path |
| low | `backend/app/tools/desktop.py` | 570 | `B603` (bandit) | subprocess call - check for execution of untrusted input. |
| low | `backend/app/tools/image_gen.py` | 20 | `B404` (bandit) | Consider possible security implications associated with the subprocess module. |
| low | `backend/app/tools/image_gen.py` | 127 | `B311` (bandit) | Standard pseudo-random generators are not suitable for security/cryptographic purposes. |
| low | `backend/app/tools/video_gen.py` | 15 | `B404` (bandit) | Consider possible security implications associated with the subprocess module. |
| low | `backend/app/tools/video_gen.py` | 175 | `B311` (bandit) | Standard pseudo-random generators are not suitable for security/cryptographic purposes. |
| low | `backend/tests/test_agent.py` | 34 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 41 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 48 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 50 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 52 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 53 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 70 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 71 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 72 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 74 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 87 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 88 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 94 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 100 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 101 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 102 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 110 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 140 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 148 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 152 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 153 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 158 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 160 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 185 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 186 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 205 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 209 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 218 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 222 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 223 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 224 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 229 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 231 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 232 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 266 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 271 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_agent.py` | 274 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 15 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 17 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 18 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 19 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 20 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 21 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 22 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 23 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 36 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 37 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 38 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_audit_log.py` | 54 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 93 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 94 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 106 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 107 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 121 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 122 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 132 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 145 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 146 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 147 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_browser_tool.py` | 148 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 51 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 59 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 60 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 68 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 76 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 84 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 92 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 100 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_graph.py` | 107 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 36 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 37 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 38 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 39 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 47 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 48 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 49 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 52 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 53 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 60 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 67 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 75 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 77 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 78 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 79 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 87 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 89 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 90 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 98 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 99 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 101 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_indexer.py` | 107 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 27 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 32 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 34 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 35 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 40 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 47 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 49 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 54 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 59 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 70 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 73 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 74 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 79 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 84 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 86 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 87 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 88 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 93 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 98 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 107 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 115 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 116 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_router.py` | 125 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_store.py` | 24 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_store.py` | 26 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_store.py` | 36 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_store.py` | 46 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_store.py` | 50 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_store.py` | 58 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_store.py` | 59 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 26 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 27 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 28 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 37 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 38 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 51 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 53 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_codebase_tools.py` | 54 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 124 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 125 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 130 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 131 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 136 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 137 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 142 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 143 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 148 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 153 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 154 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 159 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 164 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 177 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 187 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 188 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 203 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 204 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 222 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 223 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |
| low | `backend/tests/test_desktop_tools.py` | 224 | `B101` (bandit) | Use of assert detected. The enclosed code will be removed when compiling to optimised byte code. |

_(+377 más, omitidos por espacio)_

## Hallazgos de calidad (61)

| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |
|---|---|---|---|---|
| high | `backend/app/agent.py` | 175 | `call-overload` (mypy) | No overload variant of "create" of "AsyncCompletions" matches argument types "str", "list[dict[Any, Any]]", "list[dict[Any, Any]] \| None", "str \| None" |
| high | `backend/app/codebase/indexer.py` | 98 | `union-attr` (mypy) | Item "None" of "bytes \| None" has no attribute "decode" |
| high | `backend/app/codebase/indexer.py` | 100 | `union-attr` (mypy) | Item "None" of "bytes \| None" has no attribute "decode" |
| high | `backend/app/network_info.py` | 46 | `arg-type` (mypy) | Argument 1 to "add" of "set" has incompatible type "str \| int"; expected "str" |
| high | `backend/app/network_info.py` | 47 | `arg-type` (mypy) | Argument 1 to "append" of "list" has incompatible type "str \| int"; expected "str" |
| high | `backend/app/obsidian/vault.py` | 87 | `arg-type` (mypy) | Argument "title" to "VaultNote" has incompatible type "object"; expected "str" |
| high | `backend/app/obsidian/vault.py` | 88 | `arg-type` (mypy) | Argument "author" to "VaultNote" has incompatible type "object"; expected "str" |
| high | `backend/app/obsidian/vault.py` | 89 | `call-overload` (mypy) | No overload variant of "list" matches argument type "object" |
| high | `backend/app/obsidian/vault.py` | 90 | `arg-type` (mypy) | Argument "created" to "VaultNote" has incompatible type "object"; expected "str" |
| high | `backend/app/obsidian/vault.py` | 91 | `arg-type` (mypy) | Argument "updated" to "VaultNote" has incompatible type "object"; expected "str" |
| high | `backend/app/obsidian/vault.py` | 194 | `arg-type` (mypy) | Argument 1 to "add" of "set" has incompatible type "tuple[str, ...]"; expected "tuple[str, str]" |
| high | `backend/app/tools/phone.py` | 70 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 92 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 112 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 133 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 150 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 173 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 190 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 204 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 224 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 263 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 298 | `return` (mypy) | Missing return statement |
| high | `backend/app/tools/phone.py` | 335 | `return` (mypy) | Missing return statement |
| high | `backend/tests/test_desktop_tools.py` | 47 | `assignment` (mypy) | Incompatible types in assignment (expression has type "str", variable has type "None") |
| high | `backend/tests/test_desktop_tools.py` | 48 | `assignment` (mypy) | Incompatible types in assignment (expression has type "str", variable has type "None") |
| high | `backend/tests/test_video_frames.py` | 14 | `attr-defined` (mypy) | Module has no attribute "VideoWriter_fourcc" |
| high | `tray-app/icon.py` | 31 | `return-value` (mypy) | Incompatible return value type (got "FreeTypeFont", expected "ImageFont") |
| high | `tray-app/icon.py` | 32 | `return-value` (mypy) | Incompatible return value type (got "FreeTypeFont \| ImageFont", expected "ImageFont") |
| high | `tray-app/process_manager.py` | 39 | `arg-type` (mypy) | Argument 1 to "_find_listening_pid" has incompatible type "str"; expected "int" |
| high | `tray-app/process_manager.py` | 47 | `arg-type` (mypy) | Argument 1 to "_find_listening_pid" has incompatible type "str"; expected "int" |
| high | `tray-app/process_manager.py` | 88 | `arg-type` (mypy) | Argument 1 to "_find_listening_pid" has incompatible type "str"; expected "int" |
| high | `tray-app/ui/chat_view.py` | 212 | `arg-type` (mypy) | Argument 2 to "ChatRequestThread" has incompatible type "str \| None"; expected "str" |
| high | `tray-app/voice_listener.py` | 190 | `attr-defined` (mypy) | "None" has no attribute "reset" |
| high | `tray-app/voice_listener.py` | 202 | `attr-defined` (mypy) | "None" has no attribute "predict" |
| high | `tray-app/voice_listener.py` | 212 | `attr-defined` (mypy) | "None" has no attribute "reset" |
| high | `tray-app/voice_listener.py` | 232 | `attr-defined` (mypy) | "None" has no attribute "reset_states" |
| high | `tray-app/voice_listener.py` | 249 | `attr-defined` (mypy) | "None" has no attribute "predict" |
| high | `tray-app/voice_listener.py` | 274 | `attr-defined` (mypy) | "None" has no attribute "transcribe" |
| medium | `backend/app/quality/scanners.py` | 137 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/quality/scanners.py` | 142 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/quality/scanners.py` | 213 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/quality/scanners.py` | 285 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/quality/scanners.py` | 293 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/quality/scanners.py` | 339 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/quality/scanners.py` | 390 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/quality/scanners.py` | 397 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/routers/codebase.py` | 30 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/routers/codebase.py` | 39 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/routers/codebase.py` | 58 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/routers/codebase.py` | 70 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/routers/obsidian.py` | 41 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/routers/obsidian.py` | 58 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/security/scanners.py` | 57 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/security/scanners.py` | 62 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/security/scanners.py` | 117 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/security/scanners.py` | 125 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/security/scanners.py` | 168 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `backend/app/security/scanners.py` | 173 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `tray-app/tests/test_chat_view.py` | 42 | `B905` (ruff) | `zip()` without an explicit `strict=` parameter |
| low | `backend/tests/test_obsidian_vault.py` | 158 | `F841` (ruff) | Local variable `a` is assigned to but never used |
| low | `backend/tests/test_smoke.py` | 3 | `F401` (ruff) | `app.config.settings` imported but unused |

## Fixes aplicados (0)

Ninguno todavía.

## Ediciones generales auditadas (1)

Escrituras vía fs_write_file dentro de este proyecto (ya indexado por Codebase y con git) -- no vienen de un hallazgo puntual, pero pasan por el mismo circuito auditado y reversible.

| Commit | Archivo |
|---|---|
| `5df4c13` | `docs/jarvis_audit_flow_test.md` |