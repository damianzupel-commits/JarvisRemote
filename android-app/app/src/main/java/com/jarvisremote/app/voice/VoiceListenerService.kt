package com.jarvisremote.app.voice

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.ToneGenerator
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.jarvisremote.app.MainActivity
import com.jarvisremote.app.data.ChatRepository
import com.jarvisremote.app.data.SettingsRepository
import kotlin.coroutines.resume
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Foreground service (tipo microphone) de escucha continua: detecta "hey Jarvis"
 * on-device ([OnnxWakeWordDetector]), transcribe el comando que sigue con el
 * [SpeechRecognizer] del sistema (on-device si el dispositivo lo soporta) y lo
 * manda al backend por el mismo `/api/chat` que usa el chat de la app.
 *
 * Restricciones de Android que condicionan el diseño (ver también el manifest):
 *  - Android 14+ NO permite arrancar un FGS de micrófono desde el background ni
 *    desde BOOT_COMPLETED: este servicio solo se arranca desde la UI (toggle en
 *    Ajustes) con la app en primer plano, y tras un reinicio del celular queda
 *    apagado hasta que el usuario abra la app (a diferencia de PhoneLinkService,
 *    que sí se auto-levanta en el BootReceiver).
 *  - El micrófono es exclusivo: antes de lanzar SpeechRecognizer se libera el
 *    AudioRecord propio, y se re-crea al volver a la fase de wake word. Si otra
 *    app captura audio (llamada, etc.), el read() devuelve error o silencio y el
 *    loop reintenta con backoff hasta recuperar el micrófono.
 */
class VoiceListenerService : Service() {

    enum class VoiceState { LOADING, LISTENING, TRANSCRIBING, PROCESSING, MIC_UNAVAILABLE, ERROR }

    companion object {
        private const val TAG = "VoiceListenerService"
        private const val CHANNEL_ID = "jarvis_voice"
        private const val REPLY_CHANNEL_ID = "jarvis_voice_replies"
        private const val NOTIFICATION_ID = 2
        private const val REPLY_NOTIFICATION_ID = 3

        private const val SAMPLE_RATE = 16_000
        private const val FRAME_SAMPLES = WakeWordFeatureBuffers.FRAME_SAMPLES
        // Modelo custom (models/hey_jarvis.onnx en el asset "openwakeword/",
        // entrenado con TTS en 22 voces/acentos de español) reemplazó al
        // preentrenado en inglés que dejaba la voz real de Damian en 0.006-0.365
        // -- demasiado inconsistente para cualquier umbral fijo. Vuelto al 0.5
        // estándar porque el modelo custom ya está calibrado para esta frase en
        // español; validado offline (recall 0.999, fp_rate 0.08% sobre ~70
        // oraciones negativas distintas) pero la voz real de Damian con este
        // modelo nuevo TODAVÍA NO se probó en vivo -- ajustar si hace falta tras
        // esa prueba.
        private const val WAKE_THRESHOLD = 0.5f
        private const val MIC_RETRY_MS = 3_000L
        private const val RECOGNIZER_TIMEOUT_MS = 30_000L

        private val _state = MutableStateFlow(VoiceState.LOADING)
        val state: StateFlow<VoiceState> = _state.asStateFlow()

        fun start(context: Context) {
            context.startForegroundService(Intent(context, VoiceListenerService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, VoiceListenerService::class.java))
        }
    }

    private val job = SupervisorJob()
    private val scope = CoroutineScope(job + Dispatchers.IO)
    private var loopJob: Job? = null
    private var detector: OnnxWakeWordDetector? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannels()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = buildOngoingNotification("Cargando modelos de voz...")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
        if (loopJob?.isActive != true) {
            loopJob = scope.launch { runLoop() }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        // Solo cancelar: el detector lo cierra el propio loop en su finally, cuando
        // ya nadie lo está usando. Cerrarlo acá creaba una race real (crash visto en
        // el primer test de campo): la cancelación de coroutines es cooperativa y el
        // loop podía estar a mitad de un processFrame con las sesiones ONNX ya
        // cerradas -> IllegalStateException fatal que mataba el proceso entero.
        job.cancel()
        _state.value = VoiceState.LOADING
        super.onDestroy()
    }

    // ------------------------------------------------------------------- loop

    private suspend fun runLoop() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            setState(VoiceState.ERROR, "Falta el permiso de micrófono (otorgalo en Ajustes).")
            stopSelf()
            return
        }

        val localDetector = try {
            OnnxWakeWordDetector(this)
        } catch (e: Exception) {
            Log.e(TAG, "no se pudieron cargar los modelos de wake word", e)
            setState(VoiceState.ERROR, "No se pudieron cargar los modelos de voz.")
            stopSelf()
            return
        }
        detector = localDetector
        Log.i(TAG, "modelos de wake word cargados, arrancando escucha")

        try {
            listenLoop(localDetector)
        } catch (e: Throwable) {
            // Nada de acá adentro puede matar el proceso de la app. Si el job fue
            // cancelado (toggle apagado / servicio detenido), cualquier excepción
            // de teardown es esperable y se ignora; si el loop murió de verdad con
            // el servicio aún activo, se avisa y se deja el servicio parado.
            if (job.isActive) {
                Log.e(TAG, "loop de voz caído", e)
                setState(VoiceState.ERROR, "La escucha de voz se cayó: ${e.message}")
            }
        } finally {
            try {
                localDetector.close()
            } catch (_: Exception) {
                // Cerrar dos veces o sobre sesiones ya muertas no debe romper nada.
            }
            detector = null
        }
    }

    private suspend fun listenLoop(localDetector: OnnxWakeWordDetector) {
        val settingsRepository = SettingsRepository(applicationContext)
        val chatRepository = ChatRepository(settingsRepository)
        val frame = ShortArray(FRAME_SAMPLES)

        while (job.isActive) {
            val audioRecord = createAudioRecord()
            if (audioRecord == null) {
                setState(VoiceState.MIC_UNAVAILABLE, "Micrófono ocupado, reintentando...")
                delay(MIC_RETRY_MS)
                continue
            }

            setState(VoiceState.LISTENING, "Escuchando \"hey Jarvis\"...")
            localDetector.reset()
            var consecutiveReadErrors = 0
            // Instrumentación de campo: pico de score y de amplitud por ventana de
            // ~3s, para poder diagnosticar "no detecta" con números (¿el score se
            // queda a 0.4 del umbral o a 0.45? ¿el mic entrega audio con nivel
            // real o llega casi mudo?) en vez de a ciegas.
            var peakScore = 0f
            var peakAmplitude = 0
            var framesSinceLog = 0

            try {
                audioRecord.startRecording()
                while (job.isActive) {
                    val read = audioRecord.read(frame, 0, FRAME_SAMPLES, AudioRecord.READ_BLOCKING)
                    if (read != FRAME_SAMPLES) {
                        // read() < 0 es error real; 0 o parcial sostenido = otra app
                        // nos silenció/quitó el mic (política de captura concurrente
                        // de Android). En ambos casos: soltar y reintentar.
                        consecutiveReadErrors++
                        if (consecutiveReadErrors >= 5) {
                            Log.w(TAG, "micrófono perdido (read=$read), reintentando en ${MIC_RETRY_MS}ms")
                            break
                        }
                        continue
                    }
                    consecutiveReadErrors = 0

                    val score = localDetector.processFrame(frame)
                    var maxAbs = 0
                    for (s in frame) {
                        val a = if (s >= 0) s.toInt() else -s.toInt()
                        if (a > maxAbs) maxAbs = a
                    }
                    if (score > peakScore) peakScore = score
                    if (maxAbs > peakAmplitude) peakAmplitude = maxAbs
                    framesSinceLog++
                    if (framesSinceLog >= 38) { // ~3 segundos de audio
                        Log.i(TAG, "pico 3s: score=%.3f amplitud=%d/32767".format(peakScore, peakAmplitude))
                        peakScore = 0f
                        peakAmplitude = 0
                        framesSinceLog = 0
                    }

                    if (score >= WAKE_THRESHOLD) {
                        Log.i(TAG, "wake word detectada (score=$score)")
                        // Liberar el mic ANTES de SpeechRecognizer (captura exclusiva).
                        audioRecord.stop()
                        audioRecord.release()

                        playAck()
                        handleCommand(chatRepository)
                        localDetector.reset()
                        break // vuelve al while exterior, que re-crea el AudioRecord
                    }
                }
            } finally {
                try {
                    if (audioRecord.state == AudioRecord.STATE_INITIALIZED) {
                        audioRecord.release()
                    }
                } catch (_: Exception) {
                    // release() doble o sobre un record ya liberado: ignorable.
                }
            }

            if (job.isActive && consecutiveReadErrors >= 5) {
                setState(VoiceState.MIC_UNAVAILABLE, "Micrófono ocupado, reintentando...")
                delay(MIC_RETRY_MS)
            }
        }
    }

    private fun createAudioRecord(): AudioRecord? {
        val minBuffer = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuffer <= 0) return null
        return try {
            val record = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                maxOf(minBuffer, FRAME_SAMPLES * 2 * 4),
            )
            if (record.state != AudioRecord.STATE_INITIALIZED) {
                record.release()
                null
            } else {
                record
            }
        } catch (e: SecurityException) {
            Log.e(TAG, "sin permiso de micrófono", e)
            null
        } catch (e: Exception) {
            Log.e(TAG, "AudioRecord no se pudo crear", e)
            null
        }
    }

    // ------------------------------------------------------- comando + backend

    private suspend fun handleCommand(chatRepository: ChatRepository) {
        setState(VoiceState.TRANSCRIBING, "Te escucho...")
        val transcript = withTimeoutOrNull(RECOGNIZER_TIMEOUT_MS) { recognizeOnce() }

        if (transcript.isNullOrBlank()) {
            notifyReply("No te entendí — probá de nuevo diciendo \"hey Jarvis\" y tu pedido.")
            return
        }

        setState(VoiceState.PROCESSING, "Procesando: \"${transcript.take(60)}\"")
        val result = chatRepository.sendMessage(transcript)
        result.fold(
            onSuccess = { notifyReply(it.reply, heardText = transcript) },
            onFailure = { notifyReply("No pude contactar al backend: ${it.message}", heardText = transcript) },
        )
    }

    /**
     * Transcribe un comando: primero con el reconocedor on-device (API 33+ con
     * soporte) y, si ese falla por idioma (el paquete on-device de es-AR puede no
     * estar instalado — pasó en el primer test de campo: moría en ~300ms con error
     * de idioma), reintenta con el reconocedor default del sistema. El default
     * puede usar red (Google), lo cual rompe parcialmente la promesa de "todo
     * local"; se acepta como fallback documentado porque la alternativa es no
     * tener voz en absoluto en dispositivos sin el paquete de idioma local.
     *
     * SpeechRecognizer corta solo por silencio (endpointing del sistema), que es
     * justo el comportamiento que queremos para "dejar de grabar".
     */
    private suspend fun recognizeOnce(): String? {
        val onDeviceAvailable = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            SpeechRecognizer.isOnDeviceRecognitionAvailable(this)

        if (onDeviceAvailable) {
            val (text, error) = runRecognizerOnce(onDevice = true)
            if (text != null) return text
            val languageError = error == SpeechRecognizer.ERROR_LANGUAGE_NOT_SUPPORTED ||
                error == SpeechRecognizer.ERROR_LANGUAGE_UNAVAILABLE
            if (!languageError) return null
            Log.w(TAG, "recognizer on-device sin es-AR (error=$error), cayendo al del sistema")
        }

        if (!SpeechRecognizer.isRecognitionAvailable(this)) return null
        return runRecognizerOnce(onDevice = false).first
    }

    /** Un ciclo de SpeechRecognizer; devuelve (mejor hipótesis, código de error). */
    private suspend fun runRecognizerOnce(onDevice: Boolean): Pair<String?, Int?> =
        suspendCancellableCoroutine { cont ->
            val mainHandler = Handler(Looper.getMainLooper())
            mainHandler.post {
                val recognizer = try {
                    if (onDevice && Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                        SpeechRecognizer.createOnDeviceSpeechRecognizer(this)
                    } else {
                        SpeechRecognizer.createSpeechRecognizer(this)
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "no se pudo crear el SpeechRecognizer (onDevice=$onDevice)", e)
                    if (cont.isActive) cont.resume(null to null)
                    return@post
                }

                fun finish(result: String?, error: Int?) {
                    try {
                        recognizer.destroy()
                    } catch (_: Exception) {
                        // destroy() puede tirar si el recognizer ya murió; irrelevante.
                    }
                    if (cont.isActive) cont.resume(result to error)
                }

                recognizer.setRecognitionListener(object : RecognitionListener {
                    override fun onResults(results: Bundle?) {
                        val best = results
                            ?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                            ?.firstOrNull()
                        Log.i(TAG, "transcripción (onDevice=$onDevice): ${best?.take(80)}")
                        finish(best, null)
                    }

                    override fun onError(error: Int) {
                        Log.w(TAG, "SpeechRecognizer error=$error (onDevice=$onDevice)")
                        finish(null, error)
                    }

                    override fun onReadyForSpeech(params: Bundle?) {}
                    override fun onBeginningOfSpeech() {}
                    override fun onRmsChanged(rmsdB: Float) {}
                    override fun onBufferReceived(buffer: ByteArray?) {}
                    override fun onEndOfSpeech() {}
                    override fun onPartialResults(partialResults: Bundle?) {}
                    override fun onEvent(eventType: Int, params: Bundle?) {}
                })

                val intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    putExtra(RecognizerIntent.EXTRA_LANGUAGE, "es-AR")
                    putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1)
                }
                recognizer.startListening(intent)

                cont.invokeOnCancellation {
                    mainHandler.post {
                        try {
                            recognizer.cancel()
                            recognizer.destroy()
                        } catch (_: Exception) {
                            // Idem finish(): limpiar un recognizer muerto no debe romper nada.
                        }
                    }
                }
            }
        }

    // ------------------------------------------------------------ presentación

    private fun playAck() {
        // Tono + vibración: con el celular en silencio el tono no suena (el stream
        // está muteado), y en el primer test de campo eso hizo parecer que la
        // detección no funcionaba. La vibración es el ack confiable en cualquier
        // modo de sonido.
        try {
            val tone = ToneGenerator(AudioManager.STREAM_NOTIFICATION, 80)
            tone.startTone(ToneGenerator.TONE_PROP_ACK, 150)
            Handler(Looper.getMainLooper()).postDelayed({ tone.release() }, 400)
        } catch (e: Exception) {
            Log.w(TAG, "no se pudo reproducir el tono de confirmación", e)
        }
        try {
            val vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val manager = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as android.os.VibratorManager
                manager.defaultVibrator
            } else {
                @Suppress("DEPRECATION")
                getSystemService(Context.VIBRATOR_SERVICE) as android.os.Vibrator
            }
            vibrator.vibrate(android.os.VibrationEffect.createOneShot(200, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
        } catch (e: Exception) {
            Log.w(TAG, "no se pudo vibrar como confirmación", e)
        }
    }

    private fun setState(state: VoiceState, notificationText: String) {
        _state.value = state
        getSystemService(NotificationManager::class.java)
            .notify(NOTIFICATION_ID, buildOngoingNotification(notificationText))
    }

    private fun notifyReply(reply: String, heardText: String? = null) {
        val title = if (heardText != null) "Escuché: \"${heardText.take(40)}\"" else "Jarvis"
        val notification = NotificationCompat.Builder(this, REPLY_CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(reply.take(240))
            .setStyle(NotificationCompat.BigTextStyle().bigText(reply.take(1000)))
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(openAppIntent())
            .setAutoCancel(true)
            .build()
        getSystemService(NotificationManager::class.java).notify(REPLY_NOTIFICATION_ID, notification)
    }

    private fun createChannels() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "Escucha de voz", NotificationManager.IMPORTANCE_LOW),
            )
            manager.createNotificationChannel(
                NotificationChannel(REPLY_CHANNEL_ID, "Respuestas de voz", NotificationManager.IMPORTANCE_DEFAULT),
            )
        }
    }

    private fun openAppIntent(): PendingIntent = PendingIntent.getActivity(
        this,
        0,
        Intent(this, MainActivity::class.java),
        PendingIntent.FLAG_IMMUTABLE,
    )

    private fun buildOngoingNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Jarvis - hey Jarvis")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .setContentIntent(openAppIntent())
            .setOngoing(true)
            .build()
}
