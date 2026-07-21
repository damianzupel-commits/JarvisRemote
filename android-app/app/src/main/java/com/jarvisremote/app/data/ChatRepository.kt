package com.jarvisremote.app.data

import kotlinx.coroutines.flow.first

class ChatRepository(private val settingsRepository: SettingsRepository) {

    suspend fun sendMessage(text: String): Result<ChatResponse> {
        val settings = settingsRepository.settingsFlow.first()
        if (settings.backendUrl.isBlank() || settings.apiKey.isBlank()) {
            return Result.failure(IllegalStateException("Configurá la URL del backend y el API key primero."))
        }
        return try {
            val conversationId = settingsRepository.ensureConversationId()
            val resolvedUrl = BackendUrlResolver.resolve(
                backendUrl = settings.backendUrl,
                lastKnownDirectUrl = settings.lastKnownDirectUrl,
                onDirectUrlDiscovered = { settingsRepository.saveLastKnownDirectUrl(it) },
            )
            val api = ApiClientProvider.getApi(resolvedUrl, settings.apiKey)
            val response = api.chat(ChatRequest(message = text, conversationId = conversationId))
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
