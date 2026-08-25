package com.jarvisremote.app.data

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Cifra/descifra el API key antes de guardarlo en DataStore, con una clave
 * AES-256-GCM generada y guardada en el Android Keystore — la clave nunca sale
 * del keystore (hardware-backed si el dispositivo lo soporta), ni siquiera esta
 * clase ve su material en crudo, solo usa un `Cipher` inicializado con ella.
 *
 * Antes de esto, `SettingsRepository` guardaba el API key en texto plano dentro
 * del archivo de DataStore Preferences — confirmado en vivo durante la
 * auditoría de seguridad (se pudo extraer con `adb shell run-as` + `strings`
 * contra un build debug). Cualquiera con acceso al storage privado de la app
 * (ADB en un build debuggable, o acceso de root/malware en cualquier build)
 * podía leerlo directo.
 *
 * Migración: los valores guardados antes de este cambio están en texto plano y
 * no son un blob cifrado válido — `decrypt` devuelve el string tal cual si no
 * puede descifrarlo, en vez de fallar. La próxima vez que se guarde el API key
 * (`SettingsRepository.saveBackendConfig`), queda cifrado.
 *
 * **Tests JVM parciales**: la lógica de framing (IV+ciphertext) y los
 * short-circuits de string vacío SÍ se testean en JVM (ver `ApiKeyCryptoTest`).
 * Lo que NO se puede testear sin device/emulador es el round-trip de cifrado
 * real: `android.security.keystore.*` (KeyStore provider "AndroidKeyStore") solo
 * existe en el framework real de Android, y Robolectric no lo simula bien — es un
 * punto de dolor conocido. El round-trip encrypt→decrypt queda pendiente de
 * validar con un test instrumentado (`androidTest`) contra un dispositivo real.
 */
object ApiKeyCrypto {
    private const val ANDROID_KEYSTORE = "AndroidKeyStore"
    private const val KEY_ALIAS = "jarvis_api_key_encryption_key"
    private const val TRANSFORMATION = "AES/GCM/NoPadding"
    private const val GCM_IV_LENGTH_BYTES = 12
    private const val GCM_TAG_LENGTH_BITS = 128

    /**
     * Framing IV+ciphertext, aislado como funciones puras (sin Android/Keystore) para
     * poder testear en JVM la parte más propensa a bugs de índices. El material real de
     * cifrado sigue viniendo del Android Keystore (ver [encrypt]/[decrypt]).
     */
    internal fun frame(iv: ByteArray, ciphertext: ByteArray): ByteArray = iv + ciphertext

    internal fun extractIv(combined: ByteArray): ByteArray {
        require(combined.size >= GCM_IV_LENGTH_BYTES) { "Blob demasiado corto para contener el IV" }
        return combined.copyOfRange(0, GCM_IV_LENGTH_BYTES)
    }

    internal fun extractCiphertext(combined: ByteArray): ByteArray {
        require(combined.size >= GCM_IV_LENGTH_BYTES) { "Blob demasiado corto para contener el IV" }
        return combined.copyOfRange(GCM_IV_LENGTH_BYTES, combined.size)
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        val spec = KeyGenParameterSpec.Builder(
            KEY_ALIAS,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setKeySize(256)
            .build()
        keyGenerator.init(spec)
        return keyGenerator.generateKey()
    }

    /** Devuelve un string listo para guardar en DataStore (base64 de iv+ciphertext). */
    fun encrypt(plaintext: String): String {
        if (plaintext.isEmpty()) return ""
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val iv = cipher.iv
        val ciphertext = cipher.doFinal(plaintext.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(frame(iv, ciphertext), Base64.NO_WRAP)
    }

    /** Reversa de [encrypt]. Ver nota de migración arriba sobre el fallback. */
    fun decrypt(stored: String): String {
        if (stored.isEmpty()) return ""
        return try {
            val combined = Base64.decode(stored, Base64.NO_WRAP)
            val iv = extractIv(combined)
            val ciphertext = extractCiphertext(combined)
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv))
            String(cipher.doFinal(ciphertext), Charsets.UTF_8)
        } catch (e: Exception) {
            stored
        }
    }
}
