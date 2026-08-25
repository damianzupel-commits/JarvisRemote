package com.jarvisremote.app.phone

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AccessibilityBlocklistTest {

    // --- Match exacto (lista configurable por el usuario) ---

    @Test
    fun `bloquea cuando el package name esta en la lista exacta`() {
        val blocked = setOf("com.google.android.apps.authenticator2", "com.mibanco.app")

        val verdict = evaluateForegroundApp("com.mibanco.app", blocked, emptyList())

        assertTrue(verdict is BlocklistVerdict.NeedsConfirmation)
        assertEquals(BlockReason.EXACT_MATCH, (verdict as BlocklistVerdict.NeedsConfirmation).reason)
    }

    @Test
    fun `no bloquea una app normal que no matchea nada`() {
        val blocked = setOf("com.mibanco.app")

        val verdict = evaluateForegroundApp("com.spotify.music", blocked, emptyList())

        assertTrue(verdict is BlocklistVerdict.Allowed)
    }

    @Test
    fun `el match exacto es case-sensitive y no hace matching parcial`() {
        val blocked = setOf("com.mibanco.app")

        // Sin patrones, un subpaquete o variante de mayúsculas no debe matchear exacto.
        assertTrue(evaluateForegroundApp("com.mibanco.app.debug", blocked, emptyList()) is BlocklistVerdict.Allowed)
        assertTrue(evaluateForegroundApp("COM.MIBANCO.APP", blocked, emptyList()) is BlocklistVerdict.Allowed)
    }

    // --- Match por patrón/categoría (banca, cripto, mensajería, etc.) ---

    @Test
    fun `bloquea por patron de categoria aunque no este en la lista exacta`() {
        // WhatsApp/bancos no están en la lista exacta pero sí en los patrones default.
        for (pkg in listOf("com.whatsapp", "org.telegram.messenger", "com.bbva.miapp", "io.metamask")) {
            val verdict = evaluateForegroundApp(pkg, emptySet())
            assertTrue("Debería bloquear $pkg", verdict is BlocklistVerdict.NeedsConfirmation)
            assertEquals(BlockReason.PATTERN_MATCH, (verdict as BlocklistVerdict.NeedsConfirmation).reason)
        }
    }

    @Test
    fun `el match por patron es case-insensitive`() {
        assertTrue(matchesAnyPattern("com.MiBanco.App", listOf("banco")))
        assertTrue(matchesAnyPattern("COM.WHATSAPP", listOf("whatsapp")))
    }

    @Test
    fun `una app normal no matchea los patrones default`() {
        val verdict = evaluateForegroundApp("com.spotify.music", emptySet())
        assertTrue(verdict is BlocklistVerdict.Allowed)
    }

    // --- Failsafe conservador (foreground desconocido) ---

    @Test
    fun `bloquea cuando el foreground es null (failsafe conservador)`() {
        val verdict = evaluateForegroundApp(null, setOf("com.mibanco.app"))
        assertTrue(verdict is BlocklistVerdict.NeedsConfirmation)
        assertEquals(BlockReason.UNKNOWN_FOREGROUND, (verdict as BlocklistVerdict.NeedsConfirmation).reason)
    }

    @Test
    fun `bloquea cuando el foreground es vacio (failsafe conservador)`() {
        val verdict = evaluateForegroundApp("", setOf("com.mibanco.app"))
        assertTrue(verdict is BlocklistVerdict.NeedsConfirmation)
        assertEquals(BlockReason.UNKNOWN_FOREGROUND, (verdict as BlocklistVerdict.NeedsConfirmation).reason)
    }

    // --- Confirmación explícita (patrón dry-run→confirm=true) ---

    @Test
    fun `con confirmacion explicita permite una app sensible`() {
        val verdict = evaluateForegroundApp("com.whatsapp", emptySet(), confirmed = true)
        assertTrue(verdict is BlocklistVerdict.Allowed)
    }

    @Test
    fun `con confirmacion explicita permite incluso un foreground desconocido`() {
        val verdict = evaluateForegroundApp(null, emptySet(), confirmed = true)
        assertTrue(verdict is BlocklistVerdict.Allowed)
    }

    // --- Helper booleano de compat ---

    @Test
    fun `isForegroundAppBlocked ahora es conservador con foreground desconocido`() {
        assertTrue(isForegroundAppBlocked(null, setOf("com.mibanco.app")))
        assertTrue(isForegroundAppBlocked("", setOf("com.mibanco.app")))
    }

    @Test
    fun `isForegroundAppBlocked permite una app normal`() {
        assertFalse(isForegroundAppBlocked("com.spotify.music", setOf("com.mibanco.app"), emptyList()))
    }
}
