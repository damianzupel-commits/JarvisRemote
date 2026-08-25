package com.jarvisremote.app.phone

/**
 * Lógica PURA (sin Android) que decide si un comando de Termux (`phone_run_command`) es
 * lo bastante peligroso como para exigir confirmación explícita antes de correr — el
 * mismo criterio que el gate del blocklist de Accessibility, pero para shell.
 *
 * NO es un sandbox: Termux corre el comando con los permisos de esa app pase lo que pase.
 * Esto es una blocklist de patrones (igual filosofía que `pc_run_command` del backend):
 * un comando destructivo, de escalada, o que toque datos/apps sensibles queda detrás de
 * `confirm=true`. La lista es heurística y conservadora — preferimos pedir confirmación de
 * más. Ver [DangerousCommandBlockedException] para el mensaje al usuario/LLM.
 */

/** Patrones (regex, case-insensitive) que marcan un comando como peligroso. */
private val DANGEROUS_COMMAND_PATTERNS: List<Regex> = listOf(
    // Borrado masivo / recursivo forzado
    """\brm\s+(-[a-z]*r[a-z]*f|-[a-z]*f[a-z]*r|-rf|-fr)\b""",
    """\brm\s+-[a-z]*\s+/""",
    """\bfind\b.*-delete\b""",
    """\bmkfs\b""",
    """\bdd\s+.*of=/dev/""",
    """\b(shred|wipe)\b""",
    // Escalada de privilegios / root
    """\b(su|sudo)\b""",
    """\btsu\b""",
    // Gestión de paquetes del sistema (desinstalar/instalar apps)
    """\bpm\s+(uninstall|disable|clear)\b""",
    """\bpkg\s+(uninstall|purge)\b""",
    """\bapt(-get)?\s+(remove|purge)\b""",
    // Acceso al almacenamiento privado de OTRAS apps (datos sensibles)
    """/data/data/(?!com\.termux\b)""",
    """/data/user/\d+/(?!com\.termux\b)""",
    // Control de dispositivo / reinicio / factory reset
    """\b(reboot|shutdown|halt)\b""",
    """\bsettings\s+put\b""",
    """\bsvc\s+(power|wifi|data)\b""",
    // Exfiltración cruda a la red
    """\b(curl|wget)\b.*\|\s*(sh|bash)\b""",
    """\bnc\b.*-e\b""",
    // Fork bomb clásica
    """:\(\)\s*\{.*\};""",
).map { Regex(it, RegexOption.IGNORE_CASE) }

/** true si `command` matchea algún patrón peligroso y por lo tanto requiere `confirm=true`. */
fun isDangerousPhoneCommand(command: String): Boolean {
    val normalized = command.trim()
    if (normalized.isEmpty()) return false
    return DANGEROUS_COMMAND_PATTERNS.any { it.containsMatchIn(normalized) }
}

/** Excepción clara para cuando un comando peligroso se frena por falta de confirmación. */
class DangerousCommandBlockedException(command: String) : Exception(
    "El comando fue frenado por seguridad: parece peligroso (borrado recursivo, escalada de " +
        "privilegios, gestión de paquetes, acceso a datos de otras apps, reinicio o exfiltración). " +
        "Reintentá con confirm=true para ejecutarlo bajo tu responsabilidad. Comando: " +
        "\"${command.take(200)}\"",
)
