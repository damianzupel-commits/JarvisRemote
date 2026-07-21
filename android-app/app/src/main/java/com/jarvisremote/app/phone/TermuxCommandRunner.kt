package com.jarvisremote.app.phone

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.core.content.ContextCompat
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicInteger
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject

/**
 * Ejecuta comandos de shell REALES en el celular delegando en Termux, vía su Intent
 * RUN_COMMAND (https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent). Tan
 * invasivo como [JarvisAccessibilityService], pero para código en vez de UI — le da
 * a Jarvis ejecución de comandos arbitrarios en el celular.
 *
 * Requiere, todo manual y NO automatizable desde acá:
 *  1. Termux instalado desde F-Droid (la versión de Play Store está deprecada y no
 *     expone RUN_COMMAND).
 *  2. `allow-external-apps=true` en `~/.termux/termux.properties`, dentro de Termux.
 *  3. El permiso Android "com.termux.permission.RUN_COMMAND" otorgado a esta app —
 *     es un permiso "dangerous": pedirlo desde Ajustes de Jarvis (ver SettingsScreen),
 *     o habilitarlo a mano en Ajustes de Android → Apps → Jarvis Remote → Permisos.
 *
 * El resultado (stdout/stderr/exit code) vuelve de forma asincrónica: Termux corre el
 * comando en su propio proceso/background y, al terminar, invoca un PendingIntent que
 * apunta a [TermuxResultService] (ver ese archivo). Se correlaciona por un id de
 * ejecución incremental que viaja como extra propio en el intent base del
 * PendingIntent — Termux preserva ese extra al hacer `pendingIntent.send()` con su
 * propio resultado como intent "fill-in". Validado en vivo contra un dispositivo real
 * (Termux 0.119.0-beta.3, versionCode 1022): las claves reales del bundle de resultado
 * son simplemente "stdout"/"stderr"/"exitCode"/"err"/"errmsg" (sin el prefijo
 * "com.termux.execute." que sugería la documentación consultada originalmente), y el
 * campo `err` no es un booleano de éxito/fracaso — un comando exitoso puede traer
 * `err=-1`; la señal confiable de que Termux rechazó el comando a nivel plugin es que
 * `errmsg` venga con contenido.
 */
object TermuxCommandRunner {

    private const val TERMUX_PACKAGE = "com.termux"
    private const val RUN_COMMAND_SERVICE_CLASS = "com.termux.app.RunCommandService"
    private const val ACTION_RUN_COMMAND = "com.termux.RUN_COMMAND"
    private const val EXTRA_COMMAND_PATH = "com.termux.RUN_COMMAND_PATH"
    private const val EXTRA_ARGUMENTS = "com.termux.RUN_COMMAND_ARGUMENTS"
    private const val EXTRA_BACKGROUND = "com.termux.RUN_COMMAND_BACKGROUND"
    private const val EXTRA_PENDING_INTENT = "com.termux.RUN_COMMAND_PENDING_INTENT"
    private const val EXTRA_RESULT_BUNDLE = "result"
    // Confirmado empíricamente contra un dispositivo real (Termux 0.119.0-beta.3,
    // versionCode 1022) vía logging crudo del bundle completo — las claves
    // "com.termux.execute.stdout"/"com.termux.execute.stderr" que había sacado de una
    // investigación previa (WebFetch sobre el código fuente de termux-app) eran
    // incorrectas para esta versión: la clave real es simplemente "stdout"/"stderr".
    private const val RESULT_STDOUT = "stdout"
    private const val RESULT_STDERR = "stderr"
    private const val RESULT_EXIT_CODE = "exitCode"
    private const val RESULT_ERR = "err"
    private const val RESULT_ERRMSG = "errmsg"
    private const val EXTRA_EXECUTION_ID = "com.jarvisremote.app.EXECUTION_ID"
    private const val TERMUX_SHELL_PATH = "/data/data/com.termux/files/usr/bin/bash"

    /** Permiso "dangerous" que define Termux; nuestra app lo declara en el manifest. */
    const val RUN_COMMAND_PERMISSION = "com.termux.permission.RUN_COMMAND"

    class TermuxPermissionMissingException : Exception(
        "Falta el permiso '$RUN_COMMAND_PERMISSION'. Otorgalo desde Ajustes de Jarvis " +
            "(\"Habilitar ejecución de comandos\") o a mano en Ajustes de Android → Apps → " +
            "Jarvis Remote → Permisos.",
    )

    class TermuxUnavailableException(cause: Throwable) : Exception(
        "No se pudo invocar a Termux (¿está instalado desde F-Droid? ¿tiene " +
            "allow-external-apps=true en ~/.termux/termux.properties?): ${cause.message}",
        cause,
    )

    private val nextExecutionId = AtomicInteger(0)
    private val pending = ConcurrentHashMap<Int, CancellableContinuation<JsonElement>>()
    private val mainHandler = Handler(Looper.getMainLooper())

    fun hasPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, RUN_COMMAND_PERMISSION) ==
            PackageManager.PERMISSION_GRANTED

    /** true si el paquete de Termux está instalado (requiere `<queries>` en el manifest). */
    fun isTermuxInstalled(context: Context): Boolean =
        try {
            context.packageManager.getPackageInfo(TERMUX_PACKAGE, 0)
            true
        } catch (_: PackageManager.NameNotFoundException) {
            false
        }

    /**
     * Corre `command` como `bash -c "<command>"` dentro de Termux y espera el resultado
     * hasta `timeoutMs`. Nunca lanza por timeout ni por falla de Termux — esos casos se
     * devuelven como parte del JSON de resultado (con 'error'/'timed_out'), igual que
     * hacen las tools de escritorio en la PC. Sí lanza si falta el permiso o si el
     * intent no se pudo ni siquiera despachar (ej. Termux no instalado).
     */
    suspend fun run(context: Context, command: String, timeoutMs: Long): JsonElement {
        if (!hasPermission(context)) throw TermuxPermissionMissingException()

        val executionId = nextExecutionId.incrementAndGet()

        return suspendCancellableCoroutine { cont ->
            pending[executionId] = cont

            val timeoutRunnable = Runnable {
                val waiting = pending.remove(executionId)
                if (waiting != null && waiting.isActive) {
                    waiting.resume(
                        buildJsonObject {
                            put("timed_out", JsonPrimitive(true))
                            put(
                                "error",
                                JsonPrimitive(
                                    "Termux no devolvió resultado dentro de ${timeoutMs}ms. " +
                                        "Verificar que esté instalado y con allow-external-apps=true.",
                                ),
                            )
                        },
                    )
                }
            }
            mainHandler.postDelayed(timeoutRunnable, timeoutMs)

            cont.invokeOnCancellation {
                mainHandler.removeCallbacks(timeoutRunnable)
                pending.remove(executionId)
            }

            val resultServiceIntent = Intent(context, TermuxResultService::class.java)
                .putExtra(EXTRA_EXECUTION_ID, executionId)
            val pendingIntentFlags = PendingIntent.FLAG_ONE_SHOT or
                (if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_MUTABLE else 0)
            val resultPendingIntent = PendingIntent.getService(
                context,
                executionId,
                resultServiceIntent,
                pendingIntentFlags,
            )

            val runIntent = Intent(ACTION_RUN_COMMAND).apply {
                setClassName(TERMUX_PACKAGE, RUN_COMMAND_SERVICE_CLASS)
                putExtra(EXTRA_COMMAND_PATH, TERMUX_SHELL_PATH)
                putExtra(EXTRA_ARGUMENTS, arrayOf("-c", command))
                putExtra(EXTRA_BACKGROUND, true)
                putExtra(EXTRA_PENDING_INTENT, resultPendingIntent)
            }

            try {
                // El wiki oficial de RUN_COMMAND usa startService (no startForegroundService) —
                // RunCommandService se promueve a foreground por su cuenta del lado de Termux.
                context.startService(runIntent)
            } catch (exc: Exception) {
                mainHandler.removeCallbacks(timeoutRunnable)
                pending.remove(executionId)
                val wrapped = if (exc is SecurityException) {
                    TermuxPermissionMissingException()
                } else {
                    TermuxUnavailableException(exc)
                }
                if (cont.isActive) cont.resumeWithException(wrapped)
            }
        }
    }

    /** Llamado por [TermuxResultService] cuando Termux manda el resultado. */
    fun deliverResult(intent: Intent) {
        val executionId = intent.getIntExtra(EXTRA_EXECUTION_ID, -1)
        val cont = pending.remove(executionId) ?: return
        if (!cont.isActive) return

        val bundle = intent.getBundleExtra(EXTRA_RESULT_BUNDLE)
        val result: JsonElement = if (bundle == null) {
            buildJsonObject {
                put("error", JsonPrimitive("Termux devolvió un resultado sin el bundle esperado"))
            }
        } else {
            // `err` NO es un booleano simple de éxito/fracaso (confirmado en vivo: un
            // comando exitoso con stdout real vino con err=-1). El indicador confiable de
            // que Termux rechazó el comando a nivel plugin (permiso, config, etc.) es que
            // mande un `errmsg` real — cuando lo manda, siempre viene con contenido; si no
            // hay errmsg, no hay error de plugin que reportar, más allá de qué numero
            // arbitrario traiga `err`.
            val errmsg = bundle.getString(RESULT_ERRMSG)
            buildJsonObject {
                put("stdout", JsonPrimitive(bundle.getString(RESULT_STDOUT) ?: ""))
                put("stderr", JsonPrimitive(bundle.getString(RESULT_STDERR) ?: ""))
                put("exit_code", JsonPrimitive(bundle.getInt(RESULT_EXIT_CODE, -1)))
                if (!errmsg.isNullOrBlank()) {
                    put("termux_error", JsonPrimitive(errmsg))
                }
            }
        }
        cont.resume(result)
    }
}
