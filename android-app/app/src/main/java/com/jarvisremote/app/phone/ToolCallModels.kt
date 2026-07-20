package com.jarvisremote.app.phone

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

/** Tool call que manda el backend por `/ws/phone` (ver `phone_link.dispatch_to_phone`). */
@Serializable
data class IncomingToolCall(
    val type: String = "tool_call",
    val id: String,
    val tool: String,
    val arguments: JsonObject = JsonObject(emptyMap()),
)

/** Respuesta que el celular manda de vuelta, correlacionada por `id` (ver `phone_link.handle_incoming`). */
@Serializable
data class OutgoingToolResult(
    val id: String,
    val result: JsonElement? = null,
    val error: String? = null,
)
