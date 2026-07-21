package com.jarvisremote.app.data

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/**
 * Test JVM puro (sin Robolectric/instrumentación) de BackendUrlResolver contra
 * servidores HTTP fake — no depende de SettingsRepository/Context a propósito,
 * ver el comentario en BackendUrlResolver.kt.
 */
class BackendUrlResolverTest {

    private lateinit var directServer: MockWebServer
    private lateinit var fallbackServer: MockWebServer

    @Before
    fun setUp() {
        directServer = MockWebServer()
        fallbackServer = MockWebServer()
    }

    @After
    fun tearDown() {
        try { directServer.shutdown() } catch (e: Exception) { /* puede ya estar cerrado */ }
        try { fallbackServer.shutdown() } catch (e: Exception) { /* puede ya estar cerrado */ }
    }

    private fun baseUrl(server: MockWebServer): String = server.url("/").toString().trimEnd('/')

    private fun healthBody(networkCandidatesJson: String = "[]"): String =
        """{"status": "ok", "phone_connected": false, "network_candidates": $networkCandidatesJson}"""

    @Test
    fun `usa el directo cacheado si responde, sin tocar el fallback`() = runTest {
        directServer.enqueue(MockResponse().setBody(healthBody()).setResponseCode(200))
        val directUrl = baseUrl(directServer)
        val fallbackUrl = baseUrl(fallbackServer)
        var discovered: String? = null

        val resolved = BackendUrlResolver.resolve(
            backendUrl = fallbackUrl,
            lastKnownDirectUrl = directUrl,
            onDirectUrlDiscovered = { discovered = it },
        )

        assertEquals(directUrl, resolved)
        assertEquals(0, fallbackServer.requestCount)
        assertNull(discovered)
    }

    @Test
    fun `cae al fallback si no hay directo cacheado`() = runTest {
        val fallbackUrl = baseUrl(fallbackServer)
        fallbackServer.enqueue(MockResponse().setBody(healthBody()).setResponseCode(200))

        val resolved = BackendUrlResolver.resolve(
            backendUrl = fallbackUrl,
            lastKnownDirectUrl = "",
            onDirectUrlDiscovered = { },
        )

        assertEquals(fallbackUrl, resolved)
    }

    @Test
    fun `cae al fallback si el directo cacheado no responde`() = runTest {
        val fallbackUrl = baseUrl(fallbackServer)
        val deadDirectUrl = baseUrl(directServer)
        directServer.shutdown() // deja de responder a propósito, simula fuera de rango

        fallbackServer.enqueue(MockResponse().setBody(healthBody()).setResponseCode(200))

        val resolved = BackendUrlResolver.resolve(
            backendUrl = fallbackUrl,
            lastKnownDirectUrl = deadDirectUrl,
            onDirectUrlDiscovered = { },
        )

        assertEquals(fallbackUrl, resolved)
    }

    @Test
    fun `descubre un candidato directo nuevo desde la respuesta del fallback`() = runTest {
        val fallbackUrl = baseUrl(fallbackServer)
        val newDirectUrl = "http://192.168.1.4:8000"
        val candidatesJson = """[{"ip": "192.168.1.4", "type": "lan", "url": "$newDirectUrl"}]"""
        fallbackServer.enqueue(MockResponse().setBody(healthBody(candidatesJson)).setResponseCode(200))
        var discovered: String? = null

        val resolved = BackendUrlResolver.resolve(
            backendUrl = fallbackUrl,
            lastKnownDirectUrl = "",
            onDirectUrlDiscovered = { discovered = it },
        )

        assertEquals(fallbackUrl, resolved)
        assertEquals(newDirectUrl, discovered)
    }

    @Test
    fun `no reporta candidato directo si network_candidates solo trae tailscale`() = runTest {
        val fallbackUrl = baseUrl(fallbackServer)
        val candidatesJson = """[{"ip": "100.64.0.1", "type": "tailscale", "url": "$fallbackUrl"}]"""
        fallbackServer.enqueue(MockResponse().setBody(healthBody(candidatesJson)).setResponseCode(200))
        var discovered: String? = null

        BackendUrlResolver.resolve(
            backendUrl = fallbackUrl,
            lastKnownDirectUrl = "",
            onDirectUrlDiscovered = { discovered = it },
        )

        assertNull(discovered)
    }

    @Test
    fun `no reporta candidato directo si coincide con el fallback`() = runTest {
        val fallbackUrl = baseUrl(fallbackServer)
        val candidatesJson = """[{"ip": "1.2.3.4", "type": "lan", "url": "$fallbackUrl"}]"""
        fallbackServer.enqueue(MockResponse().setBody(healthBody(candidatesJson)).setResponseCode(200))
        var discovered: String? = null

        BackendUrlResolver.resolve(
            backendUrl = fallbackUrl,
            lastKnownDirectUrl = "",
            onDirectUrlDiscovered = { discovered = it },
        )

        assertNull(discovered)
    }
}
