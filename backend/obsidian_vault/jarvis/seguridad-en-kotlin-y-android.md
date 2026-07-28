---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- kotlin
- android
- sast
title: Seguridad en Kotlin y Android
updated: '2026-07-28T00:00:00.000000+00:00'
---

Kotlin/Android es uno de los lenguajes que indexa Codebase — relevante en particular para el propio cliente Android de JarvisRemote (split backend/tray/android). La superficie de riesgo en Android es distinta a backend web: mucho gira en torno a qué expone el sistema operativo a *otras apps del mismo dispositivo*, y a cómo se guardan datos localmente.

## Vulnerabilidades más comunes
| Riesgo | Ejemplo del problema |
|---|---|
| Componentes exportados sin protección | `Activity`/`Service`/`BroadcastReceiver` con `android:exported="true"` invocables por cualquier app instalada |
| Intent injection | datos de un `Intent` recibido usados sin validar para construir otro Intent/acción sensible |
| Almacenamiento inseguro | secretos en `SharedPreferences` sin cifrar, o en almacenamiento externo legible por otras apps |
| WebView mal configurado | `setJavaScriptEnabled(true)` + carga de contenido no confiable + `addJavascriptInterface` expone métodos nativos al JS de la página |
| TLS mal validado | `TrustManager`/`HostnameVerifier` custom que aceptan cualquier certificado (común "para debuggear" y queda) |
| Backup habilitado sin excluir datos sensibles | `android:allowBackup="true"` sin `android:fullBackupContent` filtrando qué se respalda |
| Logs con datos sensibles | `Log.d("token", token)` — visible vía `adb logcat` en dispositivos no rooteados incluso |

## Ejemplo: componente exportado sin protección
```kotlin
// AndroidManifest.xml -- vulnerable si el Service no valida el caller
<service android:name=".RemoteControlService" android:exported="true" />

// vulnerable: cualquier app puede bindear/iniciar este servicio y mandarle comandos
class RemoteControlService : Service() {
    override fun onStartCommand(intent: Intent, flags: Int, startId: Int): Int {
        val command = intent.getStringExtra("command")
        executeCommand(command)  // sin verificar el UID/firma del caller
        return START_STICKY
    }
}
```
Mitigación: `android:exported="false"` si el componente es solo interno; si necesita ser accesible desde otra app propia, usar `android:permission` con un permiso `signature`-level (solo apps firmadas con la misma clave) en vez de dejarlo abierto a cualquiera.

## WebView: el sink de XSS/RCE local más subestimado
```kotlin
// vulnerable: JS habilitado + interfaz nativa expuesta a contenido no confiable
webView.settings.javaScriptEnabled = true
webView.addJavascriptInterface(NativeBridge(), "Android")
webView.loadUrl(untrustedUrl)
// si untrustedUrl es controlable por un atacante, su JS puede llamar a métodos de NativeBridge
```
`addJavascriptInterface` combinado con contenido no confiable es funcionalmente RCE local en versiones de Android viejas (API < 17), y sigue siendo alto riesgo en versiones nuevas si el bridge expone algo sensible (acceso a filesystem, ejecución de comandos, credenciales).

## Buenas prácticas
- `EncryptedSharedPreferences` (Jetpack Security) para cualquier dato sensible local, nunca `SharedPreferences` plano.
- Certificate pinning para conexiones a backends propios (mitiga MITM incluso si el usuario instaló un certificado raíz malicioso).
- `android:exported` explícito (no depender del default, que cambió entre versiones de Android) en cada componente del manifest.
- Ofuscación (R8/ProGuard) no es seguridad real (es trivialmente reversible) — no confiar en ella para ocultar secretos o lógica sensible, ver [[Gestión de Secretos]].

## Herramientas
Semgrep tiene rulesets Java/Kotlin (`p/kotlin`, `p/java`) que cubren buena parte de esto; para Android específicamente, MobSF (Mobile Security Framework) es la herramienta dedicada más usada para análisis estático de APKs — fuera del scope directo de [[Herramientas SAST y SCA - Resumen]] pero vale mencionarla si el foco es una app Android completa, no solo el código fuente Kotlin.
