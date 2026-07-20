package com.jarvisremote.app.data

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface BackendApi {
    @GET("api/health")
    suspend fun health(): HealthResponse

    @POST("api/chat")
    suspend fun chat(@Body request: ChatRequest): ChatResponse
}
