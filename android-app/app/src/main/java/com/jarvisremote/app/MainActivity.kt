package com.jarvisremote.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.jarvisremote.app.data.SettingsRepository
import com.jarvisremote.app.phone.PhoneLinkService
import com.jarvisremote.app.ui.theme.JarvisRemoteTheme
import com.jarvisremote.app.voice.VoiceListenerService
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            JarvisRemoteTheme {
                JarvisApp()
            }
        }
        rearmVoiceListenerIfEnabled()
    }

    /**
     * Rearma la escucha de "hey Jarvis" si el usuario la tenía prendida. Este es
     * el único camino de reactivación tras un reinicio del celular: Android 14+
     * prohíbe arrancar un foreground service de micrófono desde BOOT_COMPLETED,
     * pero acá la app está en primer plano, que es exactamente el caso permitido.
     * Arrancar un servicio que ya corre es un no-op, así que no hace falta chequear.
     */
    private fun rearmVoiceListenerIfEnabled() {
        lifecycleScope.launch {
            val settings = SettingsRepository(applicationContext).settingsFlow.first()
            val hasMicPermission = ContextCompat.checkSelfPermission(
                this@MainActivity,
                Manifest.permission.RECORD_AUDIO,
            ) == PackageManager.PERMISSION_GRANTED
            if (settings.voiceListenerEnabled && hasMicPermission) {
                VoiceListenerService.start(this@MainActivity)
            }
            // También rearmar la conexión con el backend: tras una reinstalación o
            // muerte del proceso, el restart STICKY de Android puede tardar varios
            // minutos en resucitar PhoneLinkService (visto en campo: 7 minutos de
            // "desconectado" que parecían un problema de red y eran solo esto).
            // BootReceiver cubre el reboot; esto cubre "el usuario abrió la app".
            if (settings.phoneLinkEnabled) {
                PhoneLinkService.start(this@MainActivity)
            }
        }
    }
}
