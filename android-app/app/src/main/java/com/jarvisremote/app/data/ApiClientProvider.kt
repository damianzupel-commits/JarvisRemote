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
            // Un turno de chat puede encadenar varias tool calls, cada una con su propia
            // inferencia del modelo local (30B) — visto en vivo un turno real de más de 4
            // minutos (phone_read_screen + phone_open_app + phone_list_dir + phone_read_file)
            // que el cliente cortaba a los 180s creyendo que el backend no respondía, cuando
            // en realidad seguía trabajando bien de fondo. 30 minutos da margen real.
            .readTimeout(30, TimeUnit.MINUTES)
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
