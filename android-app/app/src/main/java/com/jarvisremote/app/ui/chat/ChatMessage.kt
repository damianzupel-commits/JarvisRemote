package com.jarvisremote.app.ui.chat

import com.jarvisremote.app.data.ToolCallLog
import java.util.UUID

enum class MessageRole { USER, ASSISTANT }

data class ChatMessage(
    val id: String = UUID.randomUUID().toString(),
    val role: MessageRole,
    val text: String,
    val toolCalls: List<ToolCallLog> = emptyList(),
    val isError: Boolean = false,
)
