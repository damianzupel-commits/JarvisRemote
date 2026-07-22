package com.jarvisremote.app.phone

import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Test

class PhoneVideoTest {

    @Test
    fun `toJson incluye base64, mime type y duracion`() {
        val result = VideoCaptureResult(
            videoBase64 = "ZmFrZXZpZGVv",
            mimeType = "video/mp4",
            durationSeconds = 5,
        )

        val json = result.toJson()

        assertEquals(JsonPrimitive("ZmFrZXZpZGVv"), json["video_base64"])
        assertEquals(JsonPrimitive("video/mp4"), json["mime_type"])
        assertEquals(JsonPrimitive(5), json["duration_seconds"])
    }

    @Test
    fun `requestedDurationSeconds usa el default si no viene el argumento`() {
        val arguments = buildJsonObject {}

        assertEquals(5, requestedDurationSeconds(arguments))
    }

    @Test
    fun `requestedDurationSeconds respeta un valor valido dentro del rango`() {
        val arguments = buildJsonObject { put("duration_seconds", JsonPrimitive(8)) }

        assertEquals(8, requestedDurationSeconds(arguments))
    }

    @Test
    fun `requestedDurationSeconds acota valores por debajo del minimo`() {
        val arguments = buildJsonObject { put("duration_seconds", JsonPrimitive(0)) }

        assertEquals(1, requestedDurationSeconds(arguments))
    }

    @Test
    fun `requestedDurationSeconds acota valores negativos`() {
        val arguments = buildJsonObject { put("duration_seconds", JsonPrimitive(-5)) }

        assertEquals(1, requestedDurationSeconds(arguments))
    }

    @Test
    fun `requestedDurationSeconds acota valores por encima del maximo`() {
        val arguments = buildJsonObject { put("duration_seconds", JsonPrimitive(60)) }

        assertEquals(15, requestedDurationSeconds(arguments))
    }
}
