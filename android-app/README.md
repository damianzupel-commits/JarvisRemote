# android-app

App Android nativa (Kotlin + Jetpack Compose) que le habla al `backend` vía
Tailscale: pantalla de configuración (URL del backend + API key) y pantalla de
chat que manda mensajes a `POST /api/chat` y muestra la respuesta junto con las
tools que se ejecutaron.

Además, la app le da a Jarvis **control total del celular** (riesgo asumido
explícitamente por el usuario): un foreground service mantiene una conexión
WebSocket saliente hacia `/ws/phone` en el backend, y despacha ahí las tool
calls con `target="phone"` — control de pantalla vía Accessibility Service
(tocar, deslizar, escribir, leer cualquier app en pantalla), filesystem del
celular sandboxeado a una carpeta elegida vía Storage Access Framework, y
**ejecución de comandos de shell reales vía Termux** (código arbitrario, no
solo interacción con la UI). Ver `app/src/main/java/com/jarvisremote/app/phone/`
y la sección "Control del celular" más abajo.

## Estado: compila limpio, compilado y verificado desde línea de comandos

El proyecto se compila y se instala **sin Android Studio**, 100% por línea de
comandos. Ver `SETUP_RAPIDO.md` para el flujo completo (una sola vez
`.\setup-android-sdk.ps1`, después `.\deploy.ps1` cada vez que conectás el
celular). `gradlew.bat assembleDebug` corrió de punta a punta en esta máquina
(`BUILD SUCCESSFUL`, APK de ~17MB en
`app/build/outputs/apk/debug/app-debug.apk`).

Esa primera compilación real encontró y corrigió tres bugs que no eran
visibles solo leyendo el código:

- **Compose Compiler / Kotlin desalineados**: AGP 8.5.2 sin
  `composeOptions.kotlinCompilerExtensionVersion` explícito usaba un default
  (1.3.2) pensado para Kotlin 1.7.20, incompatible con el Kotlin 1.9.24 del
  proyecto. Fijado a 1.5.14 en `app/build.gradle.kts` (la versión correcta
  para 1.9.24 según la tabla de compatibilidad de Google).
- **`JarvisAccessibilityService.NotEnabledException` no resolvía**: estaba
  declarada dentro del `companion object`, y una clase anidada ahí adentro
  solo se accede como `Outer.Companion.Nested` — a diferencia de
  properties/funciones del companion, que sí se promueven a `Outer.miembro`.
  Se movió afuera del companion, como nested class directa de la clase.
- **`Icons.Default.Visibility` / `VisibilityOff` no resolvían**: esos íconos
  viven en `material-icons-extended`, no en `material-icons-core` (que era la
  única dependencia declarada). Se agregó `material-icons-extended`.

### Si preferís Android Studio de todas formas

1. Instalar [Android Studio](https://developer.android.com/studio).
2. `File → Open` → seleccionar la carpeta `android-app/`. El Gradle wrapper ya
   está commiteado (se generó al correr `setup-android-sdk.ps1`), así que
   Studio no debería pedir crearlo.
3. Sync de Gradle, y correr en un emulador o un celular conectado por USB con
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
3. **Ejecución de comandos (Termux)**: le da a Jarvis un shell real en el
   celular — el nivel más invasivo posible, código arbitrario en vez de solo
   UI. Tiene tres requisitos, **todos manuales, no automatizables desde la
   app**:
   1. Instalar [Termux desde F-Droid](https://f-droid.org/packages/com.termux/)
      (la versión de Play Store está deprecada y no expone el Intent
      RUN_COMMAND que usamos).
   2. Dentro de Termux, poner `allow-external-apps=true` en
      `~/.termux/termux.properties` (crear el archivo/carpeta si no existen) y
      recargar Termux (`termux-reload-settings` o reabrir la app).
   3. Botón **"Habilitar ejecución de comandos"** en esta pantalla: pide el
      permiso Android `com.termux.permission.RUN_COMMAND` (dangerous — el
      botón queda deshabilitado si Termux no está instalado, porque Android no
      conoce ese permiso hasta que la app que lo define existe).
4. **Switch "Conexión con Jarvis"**: prende un foreground service que abre y
   mantiene la conexión WebSocket saliente hacia `/ws/phone`. Se reconecta solo
   con backoff ante cortes, y se reinicia automáticamente tras un reboot del
   celular si lo dejaste prendido. En Android 13+ te va a pedir permiso de
   notificaciones (para mostrar el estado de la conexión en la barra).

Con todo eso habilitado, el LLM puede invocar desde el chat las tools
`phone_open_app`, `phone_list_dir`, `phone_read_file`, `phone_write_file`,
`phone_tap`, `phone_swipe`, `phone_type_text`, `phone_read_screen`,
`phone_global_action` y `phone_run_command` (definidas en
`backend/app/tools/phone.py`), y verlas ejecutarse en tiempo real en el
celular.

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
          SettingsRepository.kt         # DataStore: backend URL, API key (cifrado), conversation_id
          ApiKeyCrypto.kt               # cifra/descifra el API key con una clave AES-256-GCM en Android Keystore
          ChatRepository.kt             # arma el request y llama a la API
          NetworkError.kt               # mensajes de error legibles (401, timeout, sin red, ...)
        phone/
          PhoneLinkService.kt           # foreground service: WebSocket saliente a /ws/phone, reconecta con backoff
          JarvisAccessibilityService.kt # tap/swipe/type_text/read_screen/global_action
          SafFileStore.kt               # filesystem sandboxeado al árbol SAF elegido por el usuario
          PhoneToolHandler.kt           # router de tool calls recibidas -> handler correspondiente
          ToolCallModels.kt             # (de)serialización del mensaje de tool_call / resultado
          AccessibilityUtils.kt         # chequea si el Accessibility Service está habilitado
          TermuxCommandRunner.kt        # arma/despacha el Intent RUN_COMMAND a Termux y espera el resultado
          TermuxResultService.kt        # Service liviano que recibe el resultado async vía PendingIntent
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
- **Ejecución de comandos (`TermuxCommandRunner` + `TermuxResultService`)**:
  arma un Intent explícito (`setClassName("com.termux", "com.termux.app.RunCommandService")`,
  acción `com.termux.RUN_COMMAND`) con el comando como `bash -c "<command>"`,
  `RUN_COMMAND_BACKGROUND=true`, y un `PendingIntent.getService(...)` apuntando
  a `TermuxResultService` para recibir el resultado. Se correlaciona por un id
  de ejecución incremental (`ConcurrentHashMap<Int, CancellableContinuation>`)
  que viaja como extra propio en el intent base del PendingIntent — depende de
  que Termux preserve esos extras al mandar su resultado como intent "fill-in"
  (comportamiento documentado de `PendingIntent`, replica el patrón del
  ejemplo oficial del [wiki de RUN_COMMAND](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent),
  pero **no validado en un dispositivo real** — ver "Qué falta" abajo). Nunca
  lanza excepción por timeout o por error de Termux (esos casos vuelven como
  parte del JSON de resultado); sí lanza si falta el permiso Android o si ni
  siquiera se pudo despachar el intent.

## Qué falta / próximos pasos razonables

- **Blocklist de apps sensibles en el Accessibility Service (`AccessibilityBlocklist.kt`
  + `JarvisAccessibilityService.kt` + sección nueva en Ajustes) — compilado, no
  instalado, pendiente de validar en un dispositivo real.** `tap`/`swipe`/
  `typeText`/`globalAction`/`readScreen` ahora chequean la app en foreground
  (`rootInActiveWindow?.packageName`) contra `SettingsRepository.blockedPackages`
  antes de actuar, y se niegan con `SensitiveAppBlockedException` si matchea — es
  una mitigación por nombre de paquete exacto, no un sandbox real (ver el
  docstring de `isForegroundAppBlocked`, que además es la parte que sí tiene
  test unitario JVM puro, sin necesitar Android — la lógica de chequeo del
  `AccessibilityService` en sí no se puede testear sin instrumentación, mismo
  problema que el cifrado del API key). Viene con una lista default chica de
  apps de 2FA conocidas (Google Authenticator, Microsoft Authenticator, Authy);
  **falta que Damian agregue sus bancos específicos** desde Ajustes → "Apps
  bloqueadas para Jarvis" (el package name de cada banco se saca con
  `adb shell pm list packages | grep <nombre>` con el celular conectado). No se
  instaló el APK actualizado esta sesión a propósito — el celular estaba lejos
  de la PC, usándose por datos móviles como único acceso remoto, y esta feature
  no toca la conexión en sí pero cualquier reinstalación sí la corta
  momentáneamente (ver más abajo).
- **Cifrado del API key (`ApiKeyCrypto.kt` + `SettingsRepository.kt`) — pendiente
  de validar en un dispositivo real.** Compila limpio (`gradlew.bat assembleDebug`
  → BUILD SUCCESSFUL) y no rompió los tests JVM existentes, pero
  `android.security.keystore.*` solo existe en el framework real de Android — no
  hay forma de instanciar el Android Keystore en un JVM test puro (Robolectric
  tampoco lo simula bien), así que no tiene test unitario, y el flujo real
  (generar la clave, cifrar al guardar, descifrar al leer, y sobre todo la
  migración: un API key viejo guardado en texto plano ANTES de este cambio tiene
  que seguir funcionando sin que el usuario tenga que volver a tipearlo) recién
  se puede confirmar instalando el APK actualizado en el celular de Damian.
- Probar en un dispositivo real el control del celular: conectar el celular
  (ver `SETUP_RAPIDO.md`), elegir carpeta SAF, prender el switch de conexión,
  y pedirle a Jarvis desde el chat que abra una app / lea la pantalla / toque
  algo — el código compila limpio (`gradlew.bat assembleDebug` → BUILD
  SUCCESSFUL) pero todavía no se ejecutó contra un celular real ni contra el
  backend real en esta sesión.
- **Ejecución de comandos (Termux) — esto es lo menos probado de todo el
  proyecto**: nunca se corrió contra un dispositivo real con Termux instalado.
  Falta validar en concreto:
  - Que el permiso `com.termux.permission.RUN_COMMAND` efectivamente aparezca
    en el diálogo estándar de Android al tocar "Habilitar ejecución de
    comandos" (depende de que Termux ya esté instalado y haya declarado el
    permiso).
  - Que Termux corra el comando y **efectivamente invoque el
    `PendingIntent.getService`** hacia `TermuxResultService` — y sobre todo,
    que el extra propio `EXECUTION_ID` que le pusimos al intent base del
    PendingIntent **sobreviva** al `pendingIntent.send()` de Termux (esa es la
    parte del mecanismo que replica el ejemplo oficial pero que no se probó en
    vivo). Si no sobrevive, hay que cambiar la correlación por otro mecanismo
    (ej. un solo `TermuxResultService` con una cola FIFO si solo corremos un
    comando a la vez, ya que igual no hay concurrencia real esperada acá).
  - Que el parseo del bundle de resultado (`stdout`/`stderr`/`exitCode`/`err`/
    `errmsg`) tenga los nombres de key correctos para la versión de Termux que
    tenga instalada Damian (se confirmaron contra el código fuente de
    `termux-app` en GitHub, pero versiones viejas de Termux podrían diferir).
- Antes de probar contra el backend real: revisar `backend/.env` (HOST
  bindeado a la IP de Tailscale, API_KEY fijo) y que el backend esté corriendo.
- Mejoras futuras no incluidas en este scaffold inicial: historial persistente
  en el celular (hoy vive solo en memoria del backend), reintentos automáticos,
  soporte de voz, notificaciones push cuando el backend termina una tarea larga.
