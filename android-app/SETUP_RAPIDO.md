# Setup rápido (sin Android Studio)

Compilar, instalar y habilitar el control del celular por línea de comandos,
sin abrir Android Studio en ningún momento.

**Estado (2026-07-20): probado y funciona por LAN/USB.** `setup-android-sdk.ps1`
corrió completo (JDK 17, SDK cmdline-tools, licencias, `local.properties`,
wrapper) y `gradlew.bat assembleDebug --no-daemon` terminó en `BUILD
SUCCESSFUL`, generando `app/build/outputs/apk/debug/app-debug.apk` (~17MB).
Probado end-to-end con el celular por WiFi/USB usando la IP LAN de la PC.

**Pendiente: Tailscale.** El caso de uso real es conectarse desde el celular
con datos móviles (sin WiFi), lo que requiere Tailscale — la IP LAN no sirve
ahí. A esta fecha Tailscale **no está instalado** en esta PC. Ver "Instalar
Tailscale (paso manual)" más abajo — son pasos manuales, no se pueden
automatizar (instalador requiere UAC, login requiere abrir el navegador una
vez).

## Una sola vez

```powershell
cd android-app
.\setup-android-sdk.ps1
```

Instala (todo idempotente — correrlo de nuevo no rompe nada):

- **JDK 17** (Eclipse Temurin, vía `winget`)
- **Android SDK command-line tools** + `platform-tools` (trae `adb`) +
  `platforms;android-34` + `build-tools;34.0.0`, en
  `%LOCALAPPDATA%\Android\Sdk` (la misma ubicación default que usaría Android
  Studio, por si en algún momento lo instalás también)
- Genera `android-app/local.properties` apuntando a ese SDK
- Genera el **Gradle wrapper** (`gradlew.bat`, `gradlew`,
  `gradle/wrapper/gradle-wrapper.jar`) — no estaba commiteado porque el `.jar`
  es binario y no había forma de generarlo sin Gradle instalado

Puede tardar varios minutos (descarga ~280MB entre el SDK y Gradle). Si abrís
una terminal nueva después de correrlo, las variables de entorno
(`JAVA_HOME`, `ANDROID_HOME`, `PATH`) ya van a estar seteadas — quedaron
persistidas a nivel de usuario de Windows.

## Cada vez que quieras compilar + instalar en el celular

1. Conectar el celular por USB.
2. En el celular: Ajustes → Sistema → Opciones de desarrollador → activar
   **Depuración USB** (si "Opciones de desarrollador" no aparece, tocar 7
   veces "Número de compilación" en Ajustes → Acerca del teléfono para
   habilitarlas).
3. Aceptar el popup **"¿Permitir depuración USB?"** en la pantalla del
   celular. **Este es el único paso manual que no se puede evitar** — es una
   medida de seguridad de Android, no hay forma de saltearlo por línea de
   comandos.
4. Correr:

   ```powershell
   cd android-app
   .\deploy.ps1
   ```

   Esto compila (`gradlew.bat assembleDebug`), instala el APK vía `adb install
   -r` (no hace falta habilitar "orígenes desconocidos" — instalar por adb no
   pasa por ese chequeo), y habilita el Accessibility Service de Jarvis
   directamente con `adb shell settings put secure
   enabled_accessibility_services ...` (sin pisar otros servicios de
   accesibilidad que ya tuvieras prendidos, como TalkBack).

## Lo único que queda manual dentro de la app (una sola vez)

`deploy.ps1` no puede completar esto por vos: la URL del backend, el API key,
y la carpeta de Storage Access Framework viven en el almacenamiento privado de
la app (Jetpack DataStore), no son seteables por `adb shell settings`. Abrí la
app una vez y en **Configuración**:

1. Cargar la URL de Tailscale de tu PC + puerto, y el `API_KEY` de
   `backend/.env`. Botón "Probar conexión" antes de guardar.
2. "Elegir carpeta" (SAF) para el filesystem del celular.
3. Prender el switch **"Conexión con Jarvis"**.

De ahí en más, `.\deploy.ps1` es el único comando que necesitás para
recompilar y reinstalar cada vez que cambies código (el Accessibility Service
y la config de la app persisten entre reinstalaciones con `adb install -r`).

## Instalar Tailscale (paso manual)

**Estado (2026-07-20): Tailscale NO está instalado en esta PC** (se verificó
`tailscale version`, el servicio de Windows, `C:\Program Files\Tailscale\` y
`%LOCALAPPDATA%\Tailscale` — nada de eso existe). Es necesaria la IP de
Tailscale de la PC para configurar la app Android con datos móviles, así que
este paso hay que hacerlo antes de usar la app fuera de la red local.

El instalador de Windows es un MSI que pide confirmación UAC de forma
interactiva — no se puede automatizar por línea de comandos (mismo problema
que instalar el JDK). Estos dos pasos los tenés que hacer vos a mano:

**En la PC:**

1. Ir a <https://tailscale.com/download/windows> y descargar el instalador.
2. Correr el instalador descargado y aceptar el popup de UAC ("¿Permitir que
   esta app haga cambios en el dispositivo?").
3. Al terminar, Tailscale abre el navegador pidiendo login — loguearte con
   Google, Microsoft o email. **Anotá qué cuenta usás**, porque el celular
   tiene que loguearse con la misma para quedar en la misma tailnet.
4. Avisame cuando quede logueado y corro `tailscale ip -4` para conseguir la
   IP (`100.x.x.x`) y actualizar la URL del backend en esta guía y en la app.

**En el celular:**

1. Instalar la app **Tailscale** desde Play Store.
2. Abrirla y loguearse con **la misma cuenta** que usaste en la PC (paso 3 de
   arriba) — así ambos dispositivos quedan en la misma tailnet y se pueden
   ver entre sí.
3. Dejar el switch de Tailscale prendido (puede pedir permiso de VPN/"agregar
   configuración de VPN" — es esperable, Tailscale funciona como una VPN
   local).
4. En la app Jarvis Remote, en Configuración, usar `http://<ip_tailscale_pc>:8000`
   como URL del backend (en vez de la IP LAN `192.168.x.x` que se usó para las
   pruebas por WiFi) y volver a tocar "Probar conexión".

## Si algo falla

- `adb devices` no muestra nada → revisar el cable (algunos son solo de
  carga) y que "Depuración USB" esté activada.
- Muestra `unauthorized` → mirar la pantalla del celular, puede estar
  esperando que aceptes el popup.
- `deploy.ps1` dice que no encuentra `gradlew.bat` → correr
  `setup-android-sdk.ps1` primero.
- El Accessibility Service no queda habilitado (algunos fabricantes —
  Xiaomi/MIUI, Samsung con "protección de apps"— restringen esto más) →
  habilitarlo a mano desde la app: Configuración → "Abrir Ajustes de
  Accesibilidad" → Jarvis Remote.
