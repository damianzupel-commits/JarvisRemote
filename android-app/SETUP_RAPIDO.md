# Setup rápido (sin Android Studio)

Compilar, instalar y habilitar el control del celular por línea de comandos,
sin abrir Android Studio en ningún momento.

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
