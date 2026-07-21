package com.jarvisremote.app.phone

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AccessibilityBlocklistTest {

    @Test
    fun `bloquea cuando el package name esta en la lista`() {
        val blocked = setOf("com.google.android.apps.authenticator2", "com.mibanco.app")

        assertTrue(isForegroundAppBlocked("com.mibanco.app", blocked))
    }

    @Test
    fun `no bloquea cuando el package name no esta en la lista`() {
        val blocked = setOf("com.mibanco.app")

        assertFalse(isForegroundAppBlocked("com.whatsapp", blocked))
    }

    @Test
    fun `no bloquea cuando la lista esta vacia`() {
        assertFalse(isForegroundAppBlocked("com.mibanco.app", emptySet()))
    }

    @Test
    fun `no bloquea cuando el package name es null`() {
        assertFalse(isForegroundAppBlocked(null, setOf("com.mibanco.app")))
    }

    @Test
    fun `no bloquea cuando el package name es vacio`() {
        assertFalse(isForegroundAppBlocked("", setOf("com.mibanco.app")))
    }

    @Test
    fun `es sensible a mayusculas minusculas exacto, no hace matching parcial`() {
        val blocked = setOf("com.mibanco.app")

        // Un subpaquete o variante no debe matchear por accidente.
        assertFalse(isForegroundAppBlocked("com.mibanco.app.debug", blocked))
        assertFalse(isForegroundAppBlocked("COM.MIBANCO.APP", blocked))
    }
}
