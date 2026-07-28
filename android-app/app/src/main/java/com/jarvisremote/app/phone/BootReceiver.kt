package com.jarvisremote.app.phone

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.jarvisremote.app.data.SettingsRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Si el usuario había prendido la conexión con Jarvis (ver `phoneLinkEnabled` en
 * `SettingsRepository`), la reinicia después de un reboot del celular.
 *
 * A propósito NO levanta `VoiceListenerService` (la escucha de "hey Jarvis"):
 * Android 14+ prohíbe arrancar un foreground service de micrófono desde
 * BOOT_COMPLETED (el servicio crashearía con ForegroundServiceStartNotAllowedException).
 * Esa escucha se rearma cuando el usuario abre la app (ver MainActivity).
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_BOOT_COMPLETED) return

        val pendingResult = goAsync()
        val appContext = context.applicationContext
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val enabled = SettingsRepository(appContext).settingsFlow.first().phoneLinkEnabled
                if (enabled) {
                    PhoneLinkService.start(appContext)
                }
            } finally {
                pendingResult.finish()
            }
        }
    }
}
