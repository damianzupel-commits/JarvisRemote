# android-app (placeholder — próximo paso)

App nativa Android que le habla al `backend` vía Tailscale: mandás una orden en
un campo de texto (o por voz más adelante), y ves la respuesta del modelo junto
con el log de tools que ejecutó.

## Decisión técnica

**Kotlin + Jetpack Compose**, con Retrofit/OkHttp para el cliente HTTP y
DataStore para persistir la URL del backend (IP de Tailscale + puerto) y el API
key. Es el stack nativo estándar actual para Android — no hace falta React
Native/Flutter para una app tan chica y evita una segunda toolchain.

## Plan (no implementado todavía)

```
android-app/
  app/
    src/main/java/.../
      MainActivity.kt
      ui/ChatScreen.kt        # input + lista de mensajes/tool calls
      data/BackendApi.kt      # Retrofit interface (POST /api/chat, GET /api/health)
      data/SettingsStore.kt   # DataStore: backend URL + API key
    build.gradle.kts
  build.gradle.kts
  settings.gradle.kts
```

- Pantalla de configuración inicial: URL del backend (ej. `http://100.x.x.x:8000`)
  y API key, guardados en DataStore.
- Pantalla principal: input de texto → `POST /api/chat` → muestra `reply` y el
  detalle de `tool_calls` (qué tool se ejecutó, con qué argumentos, y el
  resultado).
- Requiere tener Tailscale instalado y conectado en el celular para poder
  resolver la IP del backend.

Se scaffoldea (proyecto Gradle real) en un paso siguiente, una vez que el
backend esté probado end to end.
