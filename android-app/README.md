# android-app

App Android nativa (Kotlin + Jetpack Compose) que le habla al `backend` vía
Tailscale: pantalla de configuración (URL del backend + API key) y pantalla de
chat que manda mensajes a `POST /api/chat` y muestra la respuesta junto con las
tools que se ejecutaron.

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
        ui/
          theme/                        # Color.kt, Type.kt, Theme.kt (Material3, dynamic color)
          chat/
            ChatScreen.kt                # lista de mensajes + input + detalle de tool_calls
            ChatViewModel.kt
            ChatMessage.kt
          settings/
            SettingsScreen.kt            # form URL + API key + "Probar conexión"
            SettingsViewModel.kt
      res/
        values/ (strings, themes, colors)
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

## Qué falta / próximos pasos razonables

- Verificar la compilación real en Android Studio (no se pudo hacer en esta
  sesión) y ajustar versiones si Studio sugiere un upgrade de AGP/Gradle/Compose.
- Antes de probar contra el backend real: revisar `backend/.env` (HOST
  bindeado a la IP de Tailscale, API_KEY fijo) y que el backend esté corriendo.
- Mejoras futuras no incluidas en este scaffold inicial: historial persistente
  en el celular (hoy vive solo en memoria del backend), reintentos automáticos,
  soporte de voz, notificaciones push cuando el backend termina una tarea larga.
