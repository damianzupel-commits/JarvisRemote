package com.jarvisremote.app.data

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

/**
 * Tests JVM de la parte de [ApiKeyCrypto] que NO depende del Android Keystore:
 *  - los short-circuits de string vacío (no tocan Keystore ni Base64),
 *  - el framing IV+ciphertext (funciones puras).
 *
 * El round-trip de cifrado real (encrypt→decrypt con material del "AndroidKeyStore" y
 * `android.util.Base64`) NO se puede correr acá: esas clases solo existen en el framework
 * de Android real. Queda pendiente de validar con un test instrumentado (`androidTest`)
 * en un dispositivo/emulador — ver el docstring de `ApiKeyCrypto`.
 */
class ApiKeyCryptoTest {

    @Test
    fun `encrypt de string vacio devuelve vacio sin tocar keystore`() {
        assertEquals("", ApiKeyCrypto.encrypt(""))
    }

    @Test
    fun `decrypt de string vacio devuelve vacio sin tocar keystore`() {
        assertEquals("", ApiKeyCrypto.decrypt(""))
    }

    @Test
    fun `frame concatena iv y ciphertext en ese orden`() {
        val iv = ByteArray(12) { it.toByte() }
        val ciphertext = byteArrayOf(100, 101, 102)

        val combined = ApiKeyCrypto.frame(iv, ciphertext)

        assertEquals(15, combined.size)
        assertArrayEquals(iv, combined.copyOfRange(0, 12))
        assertArrayEquals(ciphertext, combined.copyOfRange(12, 15))
    }

    @Test
    fun `extractIv y extractCiphertext son la reversa de frame`() {
        val iv = ByteArray(12) { (it * 2).toByte() }
        val ciphertext = byteArrayOf(9, 8, 7, 6, 5)

        val combined = ApiKeyCrypto.frame(iv, ciphertext)

        assertArrayEquals(iv, ApiKeyCrypto.extractIv(combined))
        assertArrayEquals(ciphertext, ApiKeyCrypto.extractCiphertext(combined))
    }

    @Test
    fun `extractIv falla si el blob es mas corto que el IV`() {
        assertThrows(IllegalArgumentException::class.java) {
            ApiKeyCrypto.extractIv(ByteArray(5))
        }
    }
}
