package com.jarvisremote.app.phone

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import com.jarvisremote.app.MainActivity
import com.jarvisremote.app.data.SettingsRepository
import kotlin.coroutines.resume
import kotlin.math.min
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * Foreground service que mantiene la conexión saliente del celular hacia
 * `/ws/phone` (ver `backend/app/phone_link.py`). Mientras esté conectado, recibe
 * tool calls con `target="phone"`, los despacha a `PhoneToolHandler`, y manda la
 * respuesta de vuelta correlacionada por `id`.
 *
 * Se reconecta solo con backoff exponencial ante cualquier corte; el estado se
 * expone vía [status] para que la UI lo muestre.
 */
class PhoneLinkService : Service() {

    enum class ConnectionStatus { DISCONNECTED, CONNECTING, CONNECTED }

    companion object {
        private const val TAG = "PhoneLinkService"
        private const val CHANNEL_ID = "jarvis_phone_link"
        private const val NOTIFICATION_ID = 1
        private const val MIN_BACKOFF_MS = 2_000L
        private const val MAX_BACKOFF_MS = 30_000L

        private val _status = MutableStateFlow(ConnectionStatus.DISCONNECTED)
        val status: StateFlow<ConnectionStatus> = _status.asStateFlow()

        fun start(context: Context) {
            val intent = Intent(context, PhoneLinkService::class.java)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, PhoneLinkService::class.java))
        }
    }

    private val job = SupervisorJob()
    private val scope = CoroutineScope(job + Dispatchers.IO)
    private var connectJob: Job? = null
    private var webSocket: WebSocket? = null
    private val json = Json { ignoreUnknownKeys = true }
    private val httpClient = OkHttpClient.Builder()
        .pingInterval(30, java.util.concurrent.TimeUnit.SECONDS)
        .build()

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification(ConnectionStatus.DISCONNECTED))
        if (connectJob == null || connectJob?.isActive != true) {
            connectJob = scope.launch { connectLoop() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        _status.value = ConnectionStatus.DISCONNECTED
        webSocket?.close(1000, "Servicio detenido")
        job.cancel()
        super.onDestroy()
    }

    private suspend fun connectLoop() {
        val settingsRepository = SettingsRepository(applicationContext)
        var backoffMs = MIN_BACKOFF_MS

        while (job.isActive) {
            val settings = settingsRepository.settingsFlow.first()
            if (settings.backendUrl.isBlank() || settings.apiKey.isBlank()) {
                delay(MIN_BACKOFF_MS)
                continue
            }

            val wsUrl = toWebSocketUrl(settings.backendUrl) + "/ws/phone"
            _status.value = ConnectionStatus.CONNECTING
            updateNotification(ConnectionStatus.CONNECTING)

            val connected = openAndAwaitClose(wsUrl, settings.apiKey)
            _status.value = ConnectionStatus.DISCONNECTED
            updateNotification(ConnectionStatus.DISCONNECTED)

            backoffMs = if (connected) MIN_BACKOFF_MS else min(backoffMs * 2, MAX_BACKOFF_MS)
            delay(backoffMs)
        }
    }

    /** Abre la conexión y suspende hasta que se cierre; devuelve true si llegó a conectar. */
    private suspend fun openAndAwaitClose(url: String, apiKey: String): Boolean =
        kotlinx.coroutines.suspendCancellableCoroutine { cont ->
            var didConnect = false
            val request = Request.Builder()
                .url(url)
                .addHeader("Authorization", "Bearer $apiKey")
                .build()

            val ws = httpClient.newWebSocket(
                request,
                object : WebSocketListener() {
                    override fun onOpen(webSocket: WebSocket, response: Response) {
                        Log.i(TAG, "WS conectado a $url")
                        didConnect = true
                        _status.value = ConnectionStatus.CONNECTED
                        updateNotification(ConnectionStatus.CONNECTED)
                    }

                    override fun onMessage(webSocket: WebSocket, text: String) {
                        handleIncoming(webSocket, text)
                    }

                    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                        Log.w(TAG, "WS cerrado (code=$code, reason=$reason)")
                        if (cont.isActive) cont.resume(didConnect)
                    }

                    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                        Log.e(TAG, "WS falló (response=${response?.code} ${response?.message})", t)
                        if (cont.isActive) cont.resume(didConnect)
                    }
                },
            )
            webSocket = ws
            cont.invokeOnCancellation { ws.cancel() }
        }

    private fun handleIncoming(webSocket: WebSocket, text: String) {
        scope.launch {
            val call = try {
                json.decodeFromString(IncomingToolCall.serializer(), text)
            } catch (e: Exception) {
                return@launch
            }
            val response = try {
                val result = PhoneToolHandler.handle(applicationContext, call.tool, call.arguments)
                OutgoingToolResult(id = call.id, result = result)
            } catch (e: Exception) {
                OutgoingToolResult(id = call.id, error = e.message ?: e.toString())
            }
            webSocket.send(json.encodeToString(OutgoingToolResult.serializer(), response))
        }
    }

    private fun toWebSocketUrl(httpBaseUrl: String): String = when {
        httpBaseUrl.startsWith("https://") -> "wss://" + httpBaseUrl.removePrefix("https://")
        httpBaseUrl.startsWith("http://") -> "ws://" + httpBaseUrl.removePrefix("http://")
        else -> httpBaseUrl
    }.trimEnd('/')

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Conexión con Jarvis",
                NotificationManager.IMPORTANCE_LOW,
            )
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    private fun buildNotification(status: ConnectionStatus): Notification {
        val openAppIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )
        val statusText = when (status) {
            ConnectionStatus.CONNECTED -> "Conectado al backend"
            ConnectionStatus.CONNECTING -> "Conectando..."
            ConnectionStatus.DISCONNECTED -> "Desconectado, reintentando..."
        }
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Jarvis Remote")
            .setContentText(statusText)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentIntent(openAppIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(status: ConnectionStatus) {
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildNotification(status))
    }
}
