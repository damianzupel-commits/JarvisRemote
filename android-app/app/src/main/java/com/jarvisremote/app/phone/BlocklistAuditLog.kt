package com.jarvisremote.app.phone

import android.content.Context
import android.util.Log
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Log local, append-only, de cada vez que el "freno de seguridad" (ver
 * [evaluateForegroundApp]) bloquea o pide confirmación de una acción — para auditoría
 * posterior. Se guarda en el storage privado de la app (`filesDir/security_audit.log`),
 * no sale del dispositivo.
 *
 * El formateo de cada línea está aislado en [formatAuditLine] (función pura, sin Android)
 * para poder testearlo en JVM; el I/O real ([record]) sí toca el filesystem de Android.
 */
object BlocklistAuditLog {

    private const val TAG = "BlocklistAudit"
    const val LOG_FILE_NAME = "security_audit.log"

    /** Qué se estaba por hacer cuando el freno actuó. */
    enum class Outcome {
        /** Se frenó y se pidió confirmación explícita (no se ejecutó). */
        BLOCKED_NEEDS_CONFIRMATION,

        /** Se ejecutó igual porque el llamador pasó confirmación explícita. */
        ALLOWED_WITH_CONFIRMATION,
    }

    /**
     * Arma una línea de log determinística (una por evento), sin depender de Android.
     * Formato: `<iso8601>\t<outcome>\t<action>\t<reason>\tpkg=<package>`
     */
    fun formatAuditLine(
        timestampMillis: Long,
        outcome: Outcome,
        action: String,
        reason: BlockReason,
        packageName: String?,
    ): String {
        val ts = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSZ", Locale.US).format(Date(timestampMillis))
        val pkg = if (packageName.isNullOrEmpty()) "<desconocido>" else packageName
        return "$ts\t$outcome\t$action\t$reason\tpkg=$pkg"
    }

    /** Escribe una línea al log local. Nunca lanza: la auditoría no debe romper la acción. */
    fun record(
        context: Context,
        outcome: Outcome,
        action: String,
        reason: BlockReason,
        packageName: String?,
        timestampMillis: Long = System.currentTimeMillis(),
    ) {
        val line = formatAuditLine(timestampMillis, outcome, action, reason, packageName)
        try {
            File(context.filesDir, LOG_FILE_NAME).appendText(line + "\n")
        } catch (e: Exception) {
            // Si no se pudo escribir el log, al menos dejamos rastro en logcat.
            Log.w(TAG, "No se pudo escribir el audit log: ${e.message}")
        }
    }
}
