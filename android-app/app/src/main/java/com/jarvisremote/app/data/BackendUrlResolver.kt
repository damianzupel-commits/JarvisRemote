package com.jarvisremote.app.data

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit

/**
 * Resuelve, en cada intento de conexión (un chat REST o un reconnect del WebSocket
 * de `PhoneLinkService`), qué URL del backend usar de verdad — sin que el usuario
 * tenga que elegir a mano entre "la de casa" y "la de Tailscale".
 *
 * Estrategia: probar primero el último candidato directo (hotspot/LAN, más rápido
 * por latencia) que haya aparecido en `network_candidates` de `/api/health`, con un
 * timeout corto; si no responde (o todavía no hay ninguno cacheado), usar la URL
 * configurada por el usuario (típicamente la de Tailscale, alcanzable "desde
 * cualquier lado"). Cualquiera de las dos que responda se aprovecha para avisar
 * (vía [onDirectUrlDiscovered]) un candidato directo nuevo/actualizado — así, apenas
 * el celular vuelve a estar en la misma red que la PC, el próximo intento ya prueba
 * la ruta corta primero, sin intervención manual.
 *
 * No depende de [SettingsRepository]/Android `Context` a propósito (recibe los
 * valores ya leídos + un callback para persistir) para poder testearse como JVM
 * test puro contra un servidor HTTP fake, sin Robolectric ni instrumentación.
 *
 * `/api/health` no requiere autenticación (ver `backend/app/main.py`), así que
 * esto no necesita el API key.
 */
object BackendUrlResolver {
    private const val PROBE_TIMEOUT_SECONDS = 3L

    private val probeClient = OkHttpClient.Builder()
        .connectTimeout(PROBE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(PROBE_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .build()

    private val json = Json { ignoreUnknownKeys = true }

    suspend fun resolve(
        backendUrl: String,
        lastKnownDirectUrl: String,
        onDirectUrlDiscovered: suspend (String) -> Unit,
    ): String {
        val fallbackUrl = normalize(backendUrl)
        val directUrl = normalize(lastKnownDirectUrl)

        if (directUrl.isNotBlank() && directUrl != fallbackUrl) {
            val health = probeHealth(directUrl)
            if (health != null) {
                notifyDirectCandidate(health, fallbackUrl, onDirectUrlDiscovered)
                return directUrl
            }
        }

        val health = probeHealth(fallbackUrl)
        if (health != null) {
            notifyDirectCandidate(health, fallbackUrl, onDirectUrlDiscovered)
        }
        return fallbackUrl
    }

    private suspend fun notifyDirectCandidate(
        health: HealthResponse,
        fallbackUrl: String,
        onDirectUrlDiscovered: suspend (String) -> Unit,
    ) {
        val direct = health.networkCandidates.firstOrNull { it.type != "tailscale" } ?: return
        val directUrl = normalize(direct.url)
        if (directUrl.isNotBlank() && directUrl != fallbackUrl) {
            onDirectUrlDiscovered(directUrl)
        }
    }

    private suspend fun probeHealth(baseUrl: String): HealthResponse? {
        if (baseUrl.isBlank()) return null
        return try {
            val retrofit = Retrofit.Builder()
                .baseUrl("$baseUrl/")
                .client(probeClient)
                .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                .build()
            retrofit.create(BackendApi::class.java).health()
        } catch (e: Exception) {
            null
        }
    }

    private fun normalize(url: String): String = url.trim().trimEnd('/')
}
