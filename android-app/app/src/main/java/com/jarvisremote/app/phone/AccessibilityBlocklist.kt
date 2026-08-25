package com.jarvisremote.app.phone

/**
 * Lógica PURA (sin dependencias de Android) del "freno de seguridad" del control por
 * Accessibility: decide si Jarvis puede actuar sobre la app que está en foreground.
 * Está separada de [JarvisAccessibilityService] a propósito para poder testearla como
 * JVM test normal (sin instrumentación / sin device).
 *
 * Modelo de seguridad (endurecido el 2026-08-17):
 *
 *  1. **Dos capas de matching**, porque no se pueden enumerar todos los bancos/apps:
 *     - `blockedPackages`: nombres de paquete EXACTOS (configurable por el usuario desde
 *       Ajustes; ver `SettingsRepository.blockedPackages`). Match case-sensitive exacto.
 *     - [DEFAULT_BLOCKED_PACKAGE_PATTERNS]: patrones por SUBSTRING (case-insensitive) que
 *       cubren categorías enteras (banca, billeteras/cripto, gestores de contraseñas,
 *       mensajería, email, Ajustes del sistema) sin tener que listar cada app una por una.
 *
 *  2. **Failsafe conservador**: si NO se puede determinar el paquete en foreground
 *     (null/vacío), el veredicto por defecto es BLOQUEAR — nunca actuar "a ciegas".
 *
 *  3. **Confirmación explícita**: una acción sobre una app sensible (o con foreground
 *     desconocido) se puede permitir solo si el llamador pasa `confirmed = true`
 *     (reutiliza el patrón dry-run→confirm=true del resto del proyecto). En ese caso
 *     el veredicto es [BlocklistVerdict.NeedsConfirmation] la primera vez y
 *     [BlocklistVerdict.Allowed] cuando `confirmed` viene en true.
 *
 * NO es un sandbox real ni una garantía completa: se apoya en el nombre de paquete que
 * reporta el sistema y en heurísticas de substring, que pueden tener falsos positivos
 * (una app legítima con "bank"/"mail" en el package) o falsos negativos (un banco con un
 * package que no matchea ningún patrón — agregarlo a mano a `blockedPackages`).
 */

/** Motivo por el que una acción quedó frenada, para el log de auditoría y el mensaje. */
enum class BlockReason {
    /** El package está en la lista exacta configurada por el usuario. */
    EXACT_MATCH,

    /** El package matcheó un patrón de categoría sensible (banca, cripto, etc.). */
    PATTERN_MATCH,

    /** No se pudo determinar la app en foreground: failsafe conservador. */
    UNKNOWN_FOREGROUND,
}

/** Resultado del chequeo de la app en foreground. */
sealed class BlocklistVerdict {
    /** La acción puede proceder. */
    object Allowed : BlocklistVerdict()

    /**
     * La app es sensible (o el foreground es desconocido) y el llamador NO confirmó:
     * la acción se rechaza hasta que el usuario/LLM la reintente con confirmación explícita.
     */
    data class NeedsConfirmation(val packageName: String?, val reason: BlockReason) : BlocklistVerdict()
}

/**
 * Patrones por SUBSTRING (case-insensitive) sobre el nombre de paquete. Cubren categorías
 * enteras de apps sensibles que no se pueden enumerar. Deliberadamente amplios: preferimos
 * un falso positivo (pedir confirmación de más) a un falso negativo (accionar sobre el
 * banco sin freno). El usuario siempre puede afinar la lista exacta desde Ajustes.
 */
val DEFAULT_BLOCKED_PACKAGE_PATTERNS: List<String> = listOf(
    // Banca / finanzas
    "bank", "banco", "bbva", "santander", "galicia", "brubank", "uala", "mercadopago",
    "financ", "visa", "mastercard", "paypal",
    // Billeteras / cripto
    "wallet", "crypto", "bitcoin", "blockchain", "binance", "coinbase", "metamask",
    "trustwallet", "exodus", "ledger",
    // Gestores de contraseñas / 2FA
    "password", "passwd", "bitwarden", "lastpass", "1password", "onepassword",
    "keepass", "dashlane", "authenticator", "authy", "2fa", "otp",
    // Mensajería
    "whatsapp", "telegram", "signal", "org.thoughtcrime.securesms", "com.facebook.orca",
    "threema", "wire.android",
    // Email
    "com.google.android.gm", "gmail", "outlook", "protonmail", "com.microsoft.office.outlook",
    "com.yahoo.mobile.client.android.mail", ".email", "emailclient",
    // Ajustes del sistema
    "com.android.settings", "settings",
)

/**
 * Núcleo del "freno de seguridad". Evalúa la app en foreground y devuelve un [BlocklistVerdict].
 *
 * @param currentPackageName paquete en foreground reportado por el sistema (null/"" = desconocido).
 * @param blockedPackages lista EXACTA configurada por el usuario.
 * @param blockedPatterns patrones de categoría (default [DEFAULT_BLOCKED_PACKAGE_PATTERNS]).
 * @param confirmed true si el llamador ya pasó una confirmación explícita (confirm=true).
 */
fun evaluateForegroundApp(
    currentPackageName: String?,
    blockedPackages: Set<String>,
    blockedPatterns: List<String> = DEFAULT_BLOCKED_PACKAGE_PATTERNS,
    confirmed: Boolean = false,
): BlocklistVerdict {
    // Failsafe conservador: sin foreground conocido, nunca accionamos a ciegas.
    if (currentPackageName.isNullOrEmpty()) {
        return if (confirmed) BlocklistVerdict.Allowed
        else BlocklistVerdict.NeedsConfirmation(currentPackageName, BlockReason.UNKNOWN_FOREGROUND)
    }

    val reason: BlockReason? = when {
        currentPackageName in blockedPackages -> BlockReason.EXACT_MATCH
        matchesAnyPattern(currentPackageName, blockedPatterns) -> BlockReason.PATTERN_MATCH
        else -> null
    }

    return when {
        reason == null -> BlocklistVerdict.Allowed
        confirmed -> BlocklistVerdict.Allowed
        else -> BlocklistVerdict.NeedsConfirmation(currentPackageName, reason)
    }
}

/** true si `packageName` contiene alguno de los `patterns` como substring (case-insensitive). */
fun matchesAnyPattern(packageName: String, patterns: List<String>): Boolean {
    val lower = packageName.lowercase()
    return patterns.any { it.isNotEmpty() && lower.contains(it.lowercase()) }
}

/**
 * Compat / atajo booleano: true si la app en foreground debe frenarse (sea por match o
 * por failsafe de foreground desconocido), sin confirmación. Reimplementado sobre
 * [evaluateForegroundApp] para que la semántica sea una sola.
 *
 * OJO — cambio de comportamiento (2026-08-17): a diferencia de la versión vieja, un
 * `currentPackageName` null/vacío ahora devuelve **true** (failsafe conservador).
 */
fun isForegroundAppBlocked(
    currentPackageName: String?,
    blockedPackages: Set<String>,
    blockedPatterns: List<String> = DEFAULT_BLOCKED_PACKAGE_PATTERNS,
): Boolean = evaluateForegroundApp(currentPackageName, blockedPackages, blockedPatterns) !is BlocklistVerdict.Allowed

/** Excepción clara para cuando una acción queda frenada por el blocklist / failsafe. */
class SensitiveAppBlockedException(packageName: String?, reason: BlockReason) : Exception(
    buildMessage(packageName, reason),
) {
    companion object {
        private fun buildMessage(packageName: String?, reason: BlockReason): String = when (reason) {
            BlockReason.UNKNOWN_FOREGROUND ->
                "Jarvis no puede accionar: no se pudo determinar qué app está en pantalla, así que por " +
                    "seguridad la acción se frena (failsafe). Reintentá con confirm=true solo si estás " +
                    "seguro de qué app está en foreground."
            BlockReason.EXACT_MATCH ->
                "Jarvis no puede actuar sobre '$packageName' ahora mismo: está en la lista de apps " +
                    "sensibles bloqueadas (Ajustes → apps bloqueadas para Jarvis). Reintentá con " +
                    "confirm=true para forzar la acción bajo tu responsabilidad."
            BlockReason.PATTERN_MATCH ->
                "Jarvis no puede actuar sobre '$packageName' ahora mismo: parece una app sensible " +
                    "(banca, billetera/cripto, gestor de contraseñas, mensajería, email o Ajustes) según " +
                    "los patrones de seguridad. Reintentá con confirm=true para forzar la acción bajo tu " +
                    "responsabilidad. Es una mitigación por nombre de paquete, no una garantía completa."
        }
    }
}
