package com.jarvisremote.app.ui.settings

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.ApiClientProvider
import com.jarvisremote.app.data.JarvisSettings
import com.jarvisremote.app.data.SettingsRepository
import com.jarvisremote.app.data.describeError
import com.jarvisremote.app.phone.PhoneLinkService
import com.jarvisremote.app.voice.SampleRecorder
import com.jarvisremote.app.voice.VoiceListenerService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

sealed interface ConnectionTestState {
    data object Idle : ConnectionTestState
    data object Testing : ConnectionTestState
    data object Success : ConnectionTestState
    data class Failure(val message: String) : ConnectionTestState
}

class SettingsViewModel(application: Application) : AndroidViewModel(application) {
    private val settingsRepository = SettingsRepository(application)

    val settings: StateFlow<JarvisSettings> = settingsRepository.settingsFlow
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), JarvisSettings("", ""))

    val phoneLinkStatus: StateFlow<PhoneLinkService.ConnectionStatus> = PhoneLinkService.status

    fun savePhoneFolderUri(uri: String) {
        viewModelScope.launch { settingsRepository.savePhoneFolderUri(uri) }
    }

    /** [rawText] es una lista separada por comas de package names (ver SettingsScreen). */
    fun saveBlockedPackages(rawText: String) {
        val packages = rawText.split(",").map { it.trim() }.filter { it.isNotEmpty() }.toSet()
        viewModelScope.launch { settingsRepository.saveBlockedPackages(packages) }
    }

    fun setPhoneLinkEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.setPhoneLinkEnabled(enabled)
            val app = getApplication<Application>()
            if (enabled) PhoneLinkService.start(app) else PhoneLinkService.stop(app)
        }
    }

    val voiceState: StateFlow<VoiceListenerService.VoiceState> = VoiceListenerService.state

    /**
     * El start acá es válido para Android 14+ porque siempre llega desde el toggle
     * de Ajustes con la app en primer plano (la única forma permitida de arrancar
     * un FGS de micrófono). El permiso RECORD_AUDIO ya viene verificado por la UI.
     */
    fun setVoiceListenerEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.setVoiceListenerEnabled(enabled)
            val app = getApplication<Application>()
            if (enabled) VoiceListenerService.start(app) else VoiceListenerService.stop(app)
        }
    }

    private val _testState = MutableStateFlow<ConnectionTestState>(ConnectionTestState.Idle)
    val testState: StateFlow<ConnectionTestState> = _testState.asStateFlow()

    fun testConnection(url: String, apiKey: String) {
        viewModelScope.launch {
            _testState.value = ConnectionTestState.Testing
            _testState.value = try {
                val api = ApiClientProvider.getApi(url, apiKey)
                val health = api.health()
                if (health.status == "ok") {
                    ConnectionTestState.Success
                } else {
                    ConnectionTestState.Failure("Respuesta inesperada del backend: ${health.status}")
                }
            } catch (e: Exception) {
                ConnectionTestState.Failure(describeError(e))
            }
        }
    }

    fun save(url: String, apiKey: String, onSaved: () -> Unit) {
        viewModelScope.launch {
            settingsRepository.saveBackendConfig(url, apiKey)
            onSaved()
        }
    }

    // --- Grabación de muestras reales para reentrenar el modelo de wake word ---
    // Ver docstring de SampleRecorder: herramienta de una sola vez, no una feature
    // permanente. `recordingLabel` es null cuando no está grabando, "positive" o
    // "negative" mientras graba (para saber qué botón deshabilitar en la UI).
    private val sampleRecorder = SampleRecorder(application)
    private val _recordingLabel = MutableStateFlow<String?>(null)
    val recordingLabel: StateFlow<String?> = _recordingLabel.asStateFlow()
    private val _lastSavedSample = MutableStateFlow<String?>(null)
    val lastSavedSample: StateFlow<String?> = _lastSavedSample.asStateFlow()

    fun startSampleRecording(label: String) {
        if (sampleRecorder.isRecording) return
        sampleRecorder.start(label)
        _recordingLabel.value = label
    }

    fun stopSampleRecording() {
        viewModelScope.launch {
            val file = sampleRecorder.stop()
            _recordingLabel.value = null
            _lastSavedSample.value = file?.name
        }
    }
}
