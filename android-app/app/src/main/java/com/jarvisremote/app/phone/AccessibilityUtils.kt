package com.jarvisremote.app.phone

import android.content.Context
import android.provider.Settings
import android.text.TextUtils

object AccessibilityUtils {
    /** Chequea el flag del sistema, no `JarvisAccessibilityService.instance` (ese solo está seteado
     * mientras el servicio está *corriendo*, y puede tardar un instante en conectarse tras habilitarlo). */
    fun isEnabled(context: Context): Boolean {
        val expected = "${context.packageName}/${JarvisAccessibilityService::class.java.name}"
        val enabledServices = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ) ?: return false
        return TextUtils.SimpleStringSplitter(':').apply { setString(enabledServices) }
            .any { it.equals(expected, ignoreCase = true) }
    }
}
