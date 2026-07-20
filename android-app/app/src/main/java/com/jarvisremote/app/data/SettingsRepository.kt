package com.jarvisremote.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "jarvis_settings")

data class JarvisSettings(
    val backendUrl: String,
    val apiKey: String,
)

class SettingsRepository(private val context: Context) {
    private object Keys {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val API_KEY = stringPreferencesKey("api_key")
        val CONVERSATION_ID = stringPreferencesKey("conversation_id")
    }

    val settingsFlow: Flow<JarvisSettings> = context.dataStore.data.map { prefs ->
        JarvisSettings(
            backendUrl = prefs[Keys.BACKEND_URL] ?: "",
            apiKey = prefs[Keys.API_KEY] ?: "",
        )
    }

    suspend fun saveBackendConfig(url: String, apiKey: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.BACKEND_URL] = url.trim().trimEnd('/')
            prefs[Keys.API_KEY] = apiKey.trim()
        }
    }

    /** conversation_id estable por instalación, para que el backend mantenga el historial. */
    suspend fun ensureConversationId(): String {
        val prefs = context.dataStore.data.first()
        prefs[Keys.CONVERSATION_ID]?.let { return it }
        val generated = UUID.randomUUID().toString()
        context.dataStore.edit { it[Keys.CONVERSATION_ID] = generated }
        return generated
    }
}
