package com.jarvisremote.app.ui.settings

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.ApiClientProvider
import com.jarvisremote.app.data.JarvisSettings
import com.jarvisremote.app.data.SettingsRepository
import com.jarvisremote.app.data.describeError
import com.jarvisremote.app.phone.PhoneLinkService
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

    fun setPhoneLinkEnabled(enabled: Boolean) {
        viewModelScope.launch {
            settingsRepository.setPhoneLinkEnabled(enabled)
            val app = getApplication<Application>()
            if (enabled) PhoneLinkService.start(app) else PhoneLinkService.stop(app)
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
}
