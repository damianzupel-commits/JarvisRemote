package com.jarvisremote.app.data

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit

private val json = Json { ignoreUnknownKeys = true }

/**
 * La URL del backend y el API key son configurables en runtime (pantalla de
 * settings), así que el cliente Retrofit/OkHttp se arma on-demand y se
 * cachea mientras no cambien.
 */
object ApiClientProvider {
    private var cachedKey: Pair<String, String>? = null
    private var cachedApi: BackendApi? = null

    @Synchronized
    fun getApi(baseUrl: String, apiKey: String): BackendApi {
        val normalizedUrl = if (baseUrl.endsWith("/")) baseUrl else "$baseUrl/"
        val key = normalizedUrl to apiKey

        cachedApi?.let { if (cachedKey == key) return it }

        val authInterceptor = Interceptor { chain ->
            val request = chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $apiKey")
                .build()
            chain.proceed(request)
        }

        val client = OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .connectTimeout(15, TimeUnit.SECONDS)
            // El modelo local (30B) + el loop de tools puede tardar bastante en responder.
            .readTimeout(180, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(normalizedUrl)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()

        val api = retrofit.create(BackendApi::class.java)
        cachedKey = key
        cachedApi = api
        return api
    }
}
