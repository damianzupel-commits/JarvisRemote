# 13 · App Android (`android-app/`)

App nativa Android que le presta a Raphael los sensores y la ejecución del teléfono. **Kotlin + Jetpack
Compose**, arquitectura MVVM. `applicationId = com.jarvisremote.app`, `minSdk 26`, `targetSdk 34`,
`compileSdk 34`. Se conecta al backend por HTTP (chat/voz) y por WebSocket saliente (`/ws/phone`) para
recibir y ejecutar tool calls con `target="phone"`.

## Dependencias clave (`app/build.gradle.kts`)
Compose (BOM, Material3, navigation, icons), Retrofit + OkHttp (+ logging + mockwebserver para tests),
kotlinx.serialization, kotlinx.coroutines, DataStore (preferences), DocumentFile (SAF), CameraX
(core/camera2/lifecycle/video), ONNX Runtime (wake word on-device).

## Capa de datos (`data/`)

- **`BackendApi.kt`** — interfaz Retrofit del backend (chat, health). `NetworkModels.kt` — DTOs
  serializables. `NetworkError.kt` — errores tipados.
- **`ChatRepository.kt`** — envía mensajes a `/api/chat` (exige URL + API key configurados).
- **`SettingsRepository.kt`** — persiste configuración en DataStore.
- **`ApiKeyCrypto.kt`** — cifra/descifra el API key con **AES-256-GCM**, con la clave en el **Android
  Keystore** (hardware-backed si el dispositivo lo soporta); la clave nunca sale del keystore. Antes se
  guardaba en texto plano en DataStore.
- **`BackendUrlResolver.kt`** — resuelve en cada intento qué URL del backend usar, sin que el usuario elija
  a mano: prueba primero el último candidato **directo** (hotspot/LAN, más rápido) de `network_candidates`
  de `/api/health`, con Tailscale como fallback. Espejo del lado del server (`network_info.py`).
- **`ApiClientProvider.kt`** — construye el cliente HTTP configurado.

## Paquete `phone/` — ejecución de tool calls del backend

- **`PhoneLinkService.kt`** — **foreground service** (tipo `dataSync`) que mantiene la conexión saliente a
  `/ws/phone`. Recibe tool calls con `target="phone"`, los despacha a `PhoneToolHandler` y devuelve la
  respuesta correlacionada por `id`. Se reconecta solo con backoff exponencial.
- **`PhoneToolHandler.kt`** — router de las tools `phone_*` (contraparte de `backend/app/tools/phone.py`);
  parsea el JSON del tool call y ejecuta el handler correspondiente. `ToolCallModels.kt` — modelos de los
  tool calls.
- **`JarvisAccessibilityService.kt`** — control genérico de pantalla (tap/swipe/type/read/global-action)
  sobre cualquier app visible, vía el **Accessibility Service** (el usuario lo habilita a mano en Ajustes →
  Accesibilidad; no se puede activar programáticamente). `AccessibilityUtils.kt`,
  `AccessibilityBlocklist.kt` + `BlocklistAuditLog.kt` (apps/acciones bloqueadas + auditoría).
- **`TermuxCommandRunner.kt`** — ejecuta comandos de shell reales delegando en **Termux** (Intent
  RUN_COMMAND); requiere el permiso `com.termux.permission.RUN_COMMAND` (que Termux define) y Termux
  instalado/configurado. `TermuxResultService.kt` recibe el resultado asincrónico vía PendingIntent.
  `DangerousPhoneCommand.kt` — blocklist de comandos destructivos (espejo del backend).
- **`SafFileStore.kt`** — filesystem del celular **sandboxeado** al árbol SAF que el usuario eligió una vez
  (mismo modelo que `FS_ALLOWED_ROOT` de la PC); cualquier `..` en el path rechaza la operación.
- **`PhoneCamera.kt` / `CameraXSupport.kt`** — foto silenciosa con CameraX (`phone_take_photo`).
  `PhoneVideo.kt` — clip corto silencioso (`phone_record_video`).
- **`BootReceiver.kt`** — re-levanta el `PhoneLinkService` tras un reinicio (pero **no** el de voz, ver
  abajo).

## Paquete `voice/` — wake word on-device

- **`VoiceListenerService.kt`** — foreground service (tipo `microphone`) de escucha continua: detecta
  "hey Jarvis" on-device, transcribe el comando con el `SpeechRecognizer` del sistema y lo manda al mismo
  `/api/chat`. Android 14+ solo permite arrancarlo con la app visible (se arranca desde el toggle de
  Ajustes) y **nunca desde BOOT_COMPLETED** — por eso tras un reinicio hay que abrir la app una vez.
- **`OnnxWakeWordDetector.kt`** — carga los modelos ONNX de openWakeWord y corre la detección on-device.
  `WakeWordFeatureBuffers.kt` — buffers de features. `SampleRecorder.kt` — captura de audio.

## Paquete `ui/` — Compose (MVVM)
`MainActivity.kt` + `JarvisApp.kt` (entrypoint), `ui/chat/` (`ChatScreen`, `ChatViewModel`,
`ChatMessage`), `ui/settings/` (`SettingsScreen`, `SettingsViewModel` — donde se otorgan los permisos
runtime y se linkea a Accesibilidad), `ui/theme/` (Compose theming).

## Permisos declarados (`AndroidManifest.xml`)
INTERNET, FOREGROUND_SERVICE (+DATA_SYNC, +MICROPHONE), POST_NOTIFICATIONS, RECEIVE_BOOT_COMPLETED,
`com.termux.permission.RUN_COMMAND`, CAMERA, RECORD_AUDIO, VIBRATE. `<queries>` para poder lanzar/consultar
cualquier app con launcher y Termux. `usesCleartextTraffic="true"` porque el backend habla HTTP plano
dentro del túnel WireGuard de Tailscale (ver [14](14-seguridad-transversal.md)).

## Seguridad del lado del teléfono (resumen)
- API key cifrado con AES-256-GCM en el Android Keystore.
- FS sandboxeado al árbol SAF elegido.
- Blocklist de comandos destructivos (`DangerousPhoneCommand`) + blocklist de accesibilidad con auditoría.
- Accessibility Service y Termux: capacidades muy invasivas, otorgadas **a mano** por el usuario, riesgo
  asumido explícitamente.

Tests en `app/src/test/` (crypto, URL resolver, blocklists, cámara, video, wake word buffers).

---

*Segunda pasada sugerida:* documentar función por función de `PhoneToolHandler` (mapeo tool→handler),
la máquina de reconexión de `PhoneLinkService` y el pipeline de `VoiceListenerService`.
