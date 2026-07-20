package com.jarvisremote.app.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
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
    /** Uri (string) del árbol SAF que el usuario eligió como sandbox de filesystem del celular. */
    val phoneFolderUri: String = "",
    /** Si el usuario pidió que el servicio de conexión arranque (y se reinicie tras un reboot). */
    val phoneLinkEnabled: Boolean = false,
)

class SettingsRepository(private val context: Context) {
    private object Keys {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val API_KEY = stringPreferencesKey("api_key")
        val CONVERSATION_ID = stringPreferencesKey("conversation_id")
        val PHONE_FOLDER_URI = stringPreferencesKey("phone_folder_uri")
        val PHONE_LINK_ENABLED = booleanPreferencesKey("phone_link_enabled")
    }

    val settingsFlow: Flow<JarvisSettings> = context.dataStore.data.map { prefs ->
        JarvisSettings(
            backendUrl = prefs[Keys.BACKEND_URL] ?: "",
            apiKey = prefs[Keys.API_KEY] ?: "",
            phoneFolderUri = prefs[Keys.PHONE_FOLDER_URI] ?: "",
            phoneLinkEnabled = prefs[Keys.PHONE_LINK_ENABLED] ?: false,
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

    suspend fun savePhoneFolderUri(uri: String) {
        context.dataStore.edit { it[Keys.PHONE_FOLDER_URI] = uri }
    }

    suspend fun setPhoneLinkEnabled(enabled: Boolean) {
        context.dataStore.edit { it[Keys.PHONE_LINK_ENABLED] = enabled }
    }
}
