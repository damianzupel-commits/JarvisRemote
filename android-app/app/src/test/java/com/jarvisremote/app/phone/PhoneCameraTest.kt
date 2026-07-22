package com.jarvisremote.app.phone

import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PhoneCameraTest {

    @Test
    fun `toJson incluye base64, mime type y dimensiones`() {
        val result = PhotoCaptureResult(
            imageBase64 = "ZmFrZQ==",
            mimeType = "image/jpeg",
            width = 1024,
            height = 768,
        )

        val json = result.toJson()

        assertEquals(JsonPrimitive("ZmFrZQ=="), json["image_base64"])
        assertEquals(JsonPrimitive("image/jpeg"), json["mime_type"])
        assertEquals(JsonPrimitive(1024), json["width"])
        assertEquals(JsonPrimitive(768), json["height"])
    }

    @Test
    fun `isFrontCameraRequested es false por default (usa la trasera)`() {
        val arguments = buildJsonObject {}

        assertFalse(isFrontCameraRequested(arguments))
    }

    @Test
    fun `isFrontCameraRequested es true solo con camera igual a front`() {
        val arguments = buildJsonObject { put("camera", JsonPrimitive("front")) }

        assertTrue(isFrontCameraRequested(arguments))
    }

    @Test
    fun `isFrontCameraRequested es false con camera igual a back`() {
        val arguments = buildJsonObject { put("camera", JsonPrimitive("back")) }

        assertFalse(isFrontCameraRequested(arguments))
    }

    @Test
    fun `isFrontCameraRequested es false con un valor invalido en vez de tirar`() {
        val arguments = buildJsonObject { put("camera", JsonPrimitive("costado")) }

        assertFalse(isFrontCameraRequested(arguments))
    }
}
