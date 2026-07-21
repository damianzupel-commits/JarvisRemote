package com.jarvisremote.app.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.core.stringSetPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "jarvis_settings")

/**
 * Punto de partida para el blocklist de apps sensibles del Accessibility Service
 * (ver `JarvisAccessibilityService`/`AccessibilityBlocklist.kt`) — solo cubre apps
 * de 2FA conocidas y de alcance global; el usuario tiene que agregar sus bancos
 * específicos desde Ajustes (el package name se puede sacar con
 * `adb shell pm list packages | grep <banco>` con el celular conectado).
 */
val DEFAULT_BLOCKED_PACKAGES = setOf(
    "com.google.android.apps.authenticator2", // Google Authenticator
    "com.azure.authenticator", // Microsoft Authenticator
    "com.authy.authy", // Twilio Authy
)

data class JarvisSettings(
    val backendUrl: String,
    val apiKey: String,
    /** Uri (string) del árbol SAF que el usuario eligió como sandbox de filesystem del celular. */
    val phoneFolderUri: String = "",
    /** Si el usuario pidió que el servicio de conexión arranque (y se reinicie tras un reboot). */
    val phoneLinkEnabled: Boolean = false,
    /**
     * Último candidato "directo" (hotspot/LAN, no Tailscale) visto en `network_candidates`
     * de `/api/health` — se prueba primero (con timeout corto) antes de caer a [backendUrl]
     * en cada intento de conexión. Ver `BackendUrlResolver`.
     */
    val lastKnownDirectUrl: String = "",
    /**
     * Package names sobre los que el Accessibility Service se niega a actuar (ver
     * `AccessibilityBlocklist.isForegroundAppBlocked`) — mitigación por nombre de
     * paquete, no una garantía completa. Configurable desde Ajustes.
     */
    val blockedPackages: Set<String> = DEFAULT_BLOCKED_PACKAGES,
)

/**
 * El API key se guarda cifrado (Android Keystore vía [ApiKeyCrypto]), no en texto
 * plano — ver el docstring de esa clase para el detalle y qué falta validar en un
 * dispositivo real. El resto de los campos no tiene datos sensibles que ameriten
 * el mismo tratamiento (la URL del backend y el candidato directo cacheado son
 * direcciones IP de la propia red del usuario, no credenciales).
 */
class SettingsRepository(private val context: Context) {
    private object Keys {
        val BACKEND_URL = stringPreferencesKey("backend_url")
        val API_KEY = stringPreferencesKey("api_key")
        val CONVERSATION_ID = stringPreferencesKey("conversation_id")
        val PHONE_FOLDER_URI = stringPreferencesKey("phone_folder_uri")
        val PHONE_LINK_ENABLED = booleanPreferencesKey("phone_link_enabled")
        val LAST_KNOWN_DIRECT_URL = stringPreferencesKey("last_known_direct_url")
        val BLOCKED_PACKAGES = stringSetPreferencesKey("blocked_packages")
    }

    val settingsFlow: Flow<JarvisSettings> = context.dataStore.data.map { prefs ->
        JarvisSettings(
            backendUrl = prefs[Keys.BACKEND_URL] ?: "",
            // El valor guardado en DataStore es el cifrado (ver ApiKeyCrypto) — se
            // descifra acá al leer, así que para el resto de la app (ViewModels,
            // ChatRepository, PhoneLinkService, SettingsScreen) `apiKey` sigue siendo
            // el string en texto plano de siempre, sin tocar ningún call site.
            apiKey = ApiKeyCrypto.decrypt(prefs[Keys.API_KEY] ?: ""),
            phoneFolderUri = prefs[Keys.PHONE_FOLDER_URI] ?: "",
            phoneLinkEnabled = prefs[Keys.PHONE_LINK_ENABLED] ?: false,
            lastKnownDirectUrl = prefs[Keys.LAST_KNOWN_DIRECT_URL] ?: "",
            blockedPackages = prefs[Keys.BLOCKED_PACKAGES] ?: DEFAULT_BLOCKED_PACKAGES,
        )
    }

    suspend fun saveBackendConfig(url: String, apiKey: String) {
        context.dataStore.edit { prefs ->
            prefs[Keys.BACKEND_URL] = url.trim().trimEnd('/')
            prefs[Keys.API_KEY] = ApiKeyCrypto.encrypt(apiKey.trim())
        }
    }

    suspend fun saveLastKnownDirectUrl(url: String) {
        context.dataStore.edit { it[Keys.LAST_KNOWN_DIRECT_URL] = url.trim().trimEnd('/') }
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

    suspend fun saveBlockedPackages(packages: Set<String>) {
        context.dataStore.edit { it[Keys.BLOCKED_PACKAGES] = packages }
    }
}
