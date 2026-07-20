# android-app

App Android nativa (Kotlin + Jetpack Compose) que le habla al `backend` vía
Tailscale: pantalla de configuración (URL del backend + API key) y pantalla de
chat que manda mensajes a `POST /api/chat` y muestra la respuesta junto con las
tools que se ejecutaron.

Además, la app le da a Jarvis **control total del celular** (riesgo asumido
explícitamente por el usuario): un foreground service mantiene una conexión
WebSocket saliente hacia `/ws/phone` en el backend, y despacha ahí las tool
calls con `target="phone"` — control de pantalla vía Accessibility Service
(tocar, deslizar, escribir, leer cualquier app en pantalla) y filesystem del
celular sandboxeado a una carpeta elegida vía Storage Access Framework. Ver
`app/src/main/java/com/jarvisremote/app/phone/` y la sección "Control del
celular" más abajo.

## Estado: scaffoldeado, no compilado en esta máquina

Esta máquina no tiene Android SDK, Gradle ni Android Studio instalados (solo un
JDK 8, insuficiente para el tooling actual de Android), así que **no pude
compilar ni correr el proyecto acá**. El código está completo y revisado a
mano, pero la primera compilación real la vas a hacer vos al abrir el proyecto.

### Abrir el proyecto

1. Instalar [Android Studio](https://developer.android.com/studio) (trae su
   propio JDK 17 y te deja instalar el Android SDK desde el wizard inicial si
   no lo tenés).
2. `File → Open` → seleccionar la carpeta `android-app/`.
3. Android Studio va a notar que falta el Gradle wrapper (`gradle-wrapper.jar`
   no está commiteado — no hay forma de generarlo sin Gradle instalado) y te
   va a ofrecer crearlo automáticamente. Aceptar. También puede sugerir
   actualizar versiones de AGP/Gradle/Compose — es esperable, el ecosistema
   Android se mueve rápido; aceptar las sugeridas por Studio está bien.
4. Sync de Gradle, y correr en un emulador o un celular conectado por USB con
   depuración habilitada.

### Antes de poder usarla de verdad

- Tener `backend/` corriendo (directo con `python run.py`, o vía la
  `tray-app/`) y accesible por Tailscale.
- Tener Tailscale instalado y conectado en el celular donde corra la app (o en
  el emulador, si le das acceso a la red del host).
- Al abrir la app por primera vez te lleva a **Configuración**: cargar la URL
  de Tailscale de tu PC + puerto (ej. `http://100.x.x.x:8000`) y el `API_KEY`
  que configuraste en `backend/.env`. Hay un botón "Probar conexión" que pega
  a `GET /api/health` con esos datos antes de guardar.

### Control del celular (opcional, control total — leer antes de habilitar)

En la misma pantalla de Configuración, sección "Control del celular":

1. **Elegir carpeta**: abre el selector de Storage Access Framework. Todo lo
   que Jarvis pueda leer/escribir en el celular (`phone_list_dir`,
   `phone_read_file`, `phone_write_file`) queda sandboxeado a esa carpeta y
   sus subcarpetas — igual que `FS_ALLOWED_ROOT` del lado de la PC.
2. **Abrir Ajustes de Accesibilidad**: te lleva a Ajustes → Accesibilidad del
   sistema para habilitar "Jarvis Remote" a mano (Android no deja activar un
   Accessibility Service programáticamente). Una vez habilitado, Jarvis puede
   leer y accionar sobre **cualquier app visible en pantalla** — incluidas
   apps de banca, 2FA, mensajería, etc. Solo habilitalo si entendés y aceptás
   ese riesgo.
3. **Switch "Conexión con Jarvis"**: prende un foreground service que abre y
   mantiene la conexión WebSocket saliente hacia `/ws/phone`. Se reconecta solo
   con backoff ante cortes, y se reinicia automáticamente tras un reboot del
   celular si lo dejaste prendido. En Android 13+ te va a pedir permiso de
   notificaciones (para mostrar el estado de la conexión en la barra).

Con las tres cosas habilitadas, el LLM puede invocar desde el chat las tools
`phone_open_app`, `phone_list_dir`, `phone_read_file`, `phone_write_file`,
`phone_tap`, `phone_swipe`, `phone_type_text`, `phone_read_screen` y
`phone_global_action` (definidas en `backend/app/tools/phone.py`), y verlas
ejecutarse en tiempo real en el celular.

## Estructura

```
android-app/
  build.gradle.kts, settings.gradle.kts, gradle.properties
  gradle/
    libs.versions.toml        # catálogo de versiones (AGP, Kotlin, Compose, Retrofit, ...)
    wrapper/gradle-wrapper.properties
  app/
    build.gradle.kts
    src/main/
      AndroidManifest.xml
      java/com/jarvisremote/app/
        MainActivity.kt
        JarvisApp.kt                    # NavHost: Settings <-> Chat
        data/
          NetworkModels.kt              # ChatRequest/ChatResponse/ToolCallLog/HealthResponse (kotlinx.serialization)
          BackendApi.kt                 # interfaz Retrofit (GET /api/health, POST /api/chat)
          ApiClientProvider.kt          # arma/cachea Retrofit+OkHttp con la URL/API key actuales
          SettingsRepository.kt         # DataStore: backend URL, API key, conversation_id
          ChatRepository.kt             # arma el request y llama a la API
          NetworkError.kt               # mensajes de error legibles (401, timeout, sin red, ...)
        phone/
          PhoneLinkService.kt           # foreground service: WebSocket saliente a /ws/phone, reconecta con backoff
          JarvisAccessibilityService.kt # tap/swipe/type_text/read_screen/global_action
          SafFileStore.kt               # filesystem sandboxeado al árbol SAF elegido por el usuario
          PhoneToolHandler.kt           # router de tool calls recibidas -> handler correspondiente
          ToolCallModels.kt             # (de)serialización del mensaje de tool_call / resultado
          AccessibilityUtils.kt         # chequea si el Accessibility Service está habilitado
          BootReceiver.kt               # reinicia PhoneLinkService tras un reboot si estaba prendido
        ui/
          theme/                        # Color.kt, Type.kt, Theme.kt (Material3, dynamic color)
          chat/
            ChatScreen.kt                # lista de mensajes + input + detalle de tool_calls
            ChatViewModel.kt
            ChatMessage.kt
          settings/
            SettingsScreen.kt            # form URL + API key + "Probar conexión" + control del celular
            SettingsViewModel.kt
      res/
        values/ (strings, themes, colors)
        xml/accessibility_service_config.xml   # capabilities declaradas del Accessibility Service
        drawable/ic_launcher_foreground.xml   # ícono placeholder (vector, sin binarios)
        mipmap-anydpi-v26/ic_launcher.xml      # ícono adaptativo
```

## Decisiones técnicas

- **Kotlin + Jetpack Compose + Material3**, con navegación via
  `navigation-compose` (dos rutas: `settings` y `chat`).
- **Retrofit + OkHttp + kotlinx.serialization** para el cliente HTTP. El
  `Authorization: Bearer <API_KEY>` se agrega en un interceptor de OkHttp.
  Timeout de lectura generosa (180s) porque un modelo local de 30B con loop de
  tools puede tardar.
- **DataStore (Preferences)** para persistir URL del backend, API key, y un
  `conversation_id` generado una vez por instalación (así el backend mantiene
  el historial de esa conversación entre aperturas de la app).
- La URL/API key son configurables en runtime (no hardcodeadas), así que el
  cliente Retrofit se reconstruye (y cachea) cada vez que cambian.
- `android:usesCleartextTraffic="true"` en el manifest: el backend habla HTTP
  plano dentro del túnel de Tailscale (que ya cifra el tráfico a nivel
  WireGuard), así que no hace falta HTTPS de punta a punta para este caso de
  uso privado. Ver el comentario en `AndroidManifest.xml`.
- Ícono de launcher: placeholder vectorial (círculo blanco + punto verde,
  mismo lenguaje visual que el ícono de la tray-app), sin depender de un PNG
  binario en el repo. Reemplazable después con el Image Asset tool de Android
  Studio.
- **Control del celular** (paquete `phone/`): foreground service
  (`PhoneLinkService`) con cliente WebSocket OkHttp, reconecta con backoff
  exponencial (2s a 30s) ante cualquier corte y expone su estado
  (`ConnectionStatus`) como `StateFlow` para la UI. El Accessibility Service
  (`JarvisAccessibilityService`) guarda su instancia activa en un companion
  object para que `PhoneToolHandler` pueda invocarlo directamente. El
  filesystem del celular (`SafFileStore`) usa `DocumentFile` sobre el árbol SAF
  persistido (`takePersistableUriPermission`), rechazando cualquier segmento
  `..` en el path — mismo modelo de sandboxing que `FS_ALLOWED_ROOT` en la PC.
  `BootReceiver` reinicia la conexión tras un reboot solo si el usuario había
  dejado el switch prendido (persistido en DataStore).

## Qué falta / próximos pasos razonables

- Verificar la compilación real en Android Studio (no se pudo hacer en esta
  sesión, no hay Android SDK acá) y ajustar versiones si Studio sugiere un
  upgrade de AGP/Gradle/Compose.
- Probar en un dispositivo real el control del celular: habilitar el
  Accessibility Service a mano, elegir carpeta SAF, prender el switch de
  conexión, y pedirle a Jarvis desde el chat que abra una app / lea la
  pantalla / toque algo — el código está escrito y revisado a mano pero no
  se pudo ejecutar en esta máquina.
- Antes de probar contra el backend real: revisar `backend/.env` (HOST
  bindeado a la IP de Tailscale, API_KEY fijo) y que el backend esté corriendo.
- Mejoras futuras no incluidas en este scaffold inicial: historial persistente
  en el celular (hoy vive solo en memoria del backend), reintentos automáticos,
  soporte de voz, notificaciones push cuando el backend termina una tarea larga.
