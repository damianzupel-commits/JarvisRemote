package com.jarvisremote.app.phone

/**
 * Chequeo puro (sin dependencias de Android) de si la app en foreground está en
 * la lista de apps sensibles bloqueadas — separado de [JarvisAccessibilityService]
 * a propósito para poder testearlo como JVM test normal, sin instrumentación.
 *
 * Es una mitigación por nombre de paquete, NO una garantía completa: se puede
 * evadir si el package name real no está en la lista (ver
 * `SettingsRepository.DEFAULT_BLOCKED_PACKAGES` — son solo un punto de partida,
 * agregar ahí los bancos/apps específicas que importen), o en teoría por una
 * ventana de tiempo entre el chequeo y la acción si la app en foreground cambia
 * justo en el medio (poco probable en la práctica, pero real).
 */
fun isForegroundAppBlocked(currentPackageName: String?, blockedPackages: Set<String>): Boolean {
    if (currentPackageName.isNullOrEmpty() || blockedPackages.isEmpty()) return false
    return currentPackageName in blockedPackages
}

/** Excepción clara para cuando [isForegroundAppBlocked] da true. */
class SensitiveAppBlockedException(packageName: String) : Exception(
    "Jarvis no puede actuar sobre '$packageName' ahora mismo: está en la lista de apps sensibles " +
        "bloqueadas (Ajustes → apps bloqueadas para Jarvis). Es una mitigación por nombre de " +
        "paquete, no una garantía de seguridad completa.",
)
