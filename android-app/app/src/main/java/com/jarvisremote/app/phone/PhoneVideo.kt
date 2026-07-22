package com.jarvisremote.app.phone

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.util.Base64
import androidx.camera.core.CameraSelector
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.core.content.ContextCompat
import java.io.File
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.intOrNull

/** Resultado de una grabación: el video crudo (sin extraer frames — eso lo hace el
 * backend, ver `video_frames.py`) más metadata liviana. */
data class VideoCaptureResult(
    val videoBase64: String,
    val mimeType: String,
    val durationSeconds: Int,
)

fun VideoCaptureResult.toJson(): JsonObject = buildJsonObject {
    put("video_base64", JsonPrimitive(videoBase64))
    put("mime_type", JsonPrimitive(mimeType))
    put("duration_seconds", JsonPrimitive(durationSeconds))
}

/** `arguments["duration_seconds"]` acotado a un rango razonable (1-15s) — un clip más
 * largo solo infla el archivo sin aportar más frames útiles (el backend extrae uno
 * cada 1-2s de todos modos, ver `video_frames.py`), y podría demorar la respuesta. */
fun requestedDurationSeconds(arguments: JsonObject, default: Int = 5, max: Int = 15): Int {
    val requested = (arguments["duration_seconds"] as? JsonPrimitive)?.intOrNull ?: default
    return requested.coerceIn(1, max)
}

interface PhoneVideoRecorder {
    /** Graba un clip de `durationSeconds` y lo devuelve. Lanza [CameraPermissionDeniedException]
     * si falta el permiso, o cualquier otra excepción si la grabación en sí falla. */
    suspend fun recordVideo(context: Context, useFrontCamera: Boolean, durationSeconds: Int): VideoCaptureResult
}

/**
 * Grabación silenciosa (sin abrir la app de Cámara) vía el `Recorder`/`VideoCapture` de
 * CameraX — mismo enfoque de [LifecycleOwner] manual de un solo uso que
 * [CameraXPhoneCamera] (ver [CameraXSupport.kt]). Sin audio (nunca se llama
 * `withAudioEnabled`): no hace falta para que un modelo de visión entienda los frames,
 * y así tampoco hace falta pedir permiso de micrófono.
 *
 * Calidad fija en [Quality.SD] — de sobra para los frames que el backend va a extraer
 * (ver `video_frames.py`), y mantiene el archivo (y el tiempo de subida por WebSocket)
 * razonable incluso a 10-15s de clip.
 *
 * No validado contra un dispositivo real todavía (pendiente de que se instale el APK).
 */
object CameraXPhoneVideoRecorder : PhoneVideoRecorder {

    override suspend fun recordVideo(
        context: Context,
        useFrontCamera: Boolean,
        durationSeconds: Int,
    ): VideoCaptureResult {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            throw CameraPermissionDeniedException()
        }

        val tempFile = File.createTempFile("jarvis_video_", ".mp4", context.cacheDir)
        try {
            recordToFile(context, tempFile, useFrontCamera, durationSeconds)
            return VideoCaptureResult(
                videoBase64 = Base64.encodeToString(tempFile.readBytes(), Base64.NO_WRAP),
                mimeType = "video/mp4",
                durationSeconds = durationSeconds,
            )
        } finally {
            tempFile.delete()
        }
    }

    private suspend fun recordToFile(
        context: Context,
        file: File,
        useFrontCamera: Boolean,
        durationSeconds: Int,
    ) {
        withContext(Dispatchers.Main) {
            val cameraProvider: ProcessCameraProvider = getCameraProvider(context)
            val lifecycleOwner = OneShotLifecycleOwner()
            val recorder = Recorder.Builder()
                .setQualitySelector(QualitySelector.from(Quality.SD))
                .build()
            val videoCapture = VideoCapture.withOutput(recorder)
            val selector = if (useFrontCamera) {
                CameraSelector.DEFAULT_FRONT_CAMERA
            } else {
                CameraSelector.DEFAULT_BACK_CAMERA
            }

            try {
                lifecycleOwner.start()
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(lifecycleOwner, selector, videoCapture)

                val finalize = CompletableDeferred<Unit>()
                val outputOptions = FileOutputOptions.Builder(file).build()
                val recording = videoCapture.output
                    .prepareRecording(context, outputOptions)
                    .start(ContextCompat.getMainExecutor(context)) { event ->
                        if (event is VideoRecordEvent.Finalize) {
                            if (event.hasError()) {
                                finalize.completeExceptionally(
                                    IllegalStateException("Error grabando video (code=${event.error})"),
                                )
                            } else {
                                finalize.complete(Unit)
                            }
                        }
                    }

                try {
                    delay(durationSeconds * 1_000L)
                } finally {
                    // Se llama tanto en el camino feliz como si `delay` se cancela/falla —
                    // asegura que la grabación se corte igual en vez de quedar colgada.
                    recording.stop()
                }
                finalize.await()
            } finally {
                cameraProvider.unbindAll()
                lifecycleOwner.destroy()
            }
        }
    }
}

/** Punto de inyección para tests: [PhoneToolHandler] usa esto en vez de la grabadora
 * real directamente, para poder mockearla sin disparar CameraX de verdad. */
object PhoneVideoProvider {
    var instance: PhoneVideoRecorder = CameraXPhoneVideoRecorder
}
