package com.jarvisremote.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

@Serializable
data class ChatRequest(
    val message: String,
    @SerialName("conversation_id") val conversationId: String? = null,
)

@Serializable
data class ChatResponse(
    @SerialName("conversation_id") val conversationId: String,
    val reply: String,
    @SerialName("tool_calls") val toolCalls: List<ToolCallLog> = emptyList(),
)

@Serializable
data class ToolCallLog(
    val tool: String,
    val arguments: JsonElement,
    val result: JsonElement,
)

@Serializable
data class NetworkCandidate(
    val ip: String,
    val type: String,
    val url: String,
)

@Serializable
data class HealthResponse(
    val status: String,
    @SerialName("phone_connected") val phoneConnected: Boolean = false,
    @SerialName("network_candidates") val networkCandidates: List<NetworkCandidate> = emptyList(),
)
