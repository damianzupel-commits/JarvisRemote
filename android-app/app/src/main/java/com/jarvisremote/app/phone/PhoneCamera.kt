package com.jarvisremote.app.phone

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Base64
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import java.io.ByteArrayOutputStream
import java.io.File
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.math.max
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull

/** Resultado de una captura, ya redimensionada/comprimida y lista para mandar por WS. */
data class PhotoCaptureResult(
    val imageBase64: String,
    val mimeType: String,
    val width: Int,
    val height: Int,
)

fun PhotoCaptureResult.toJson(): JsonObject = buildJsonObject {
    put("image_base64", JsonPrimitive(imageBase64))
    put("mime_type", JsonPrimitive(mimeType))
    put("width", JsonPrimitive(width))
    put("height", JsonPrimitive(height))
}

/** true si `arguments["camera"] == "front"`; cualquier otro valor (incluido ausente) usa la trasera. */
fun isFrontCameraRequested(arguments: JsonObject): Boolean =
    (arguments["camera"] as? JsonPrimitive)?.contentOrNull == "front"

class CameraPermissionDeniedException : Exception(
    "Permiso de cámara no otorgado. Andá a Ajustes de Jarvis > Cámara y otorgalo, o a mano en " +
        "Ajustes de Android → Apps → Jarvis Remote → Permisos.",
)

interface PhoneCamera {
    /** Captura una foto y la devuelve redimensionada/comprimida. Lanza [CameraPermissionDeniedException]
     * si falta el permiso, o cualquier otra excepción si la captura en sí falla. */
    suspend fun takePhoto(context: Context, useFrontCamera: Boolean): PhotoCaptureResult
}

/**
 * Captura silenciosa (sin abrir la app de Cámara ni esperar que el usuario apriete el
 * obturador) vía CameraX. Redimensiona al lado más largo a [MAX_DIMENSION]px y comprime
 * a JPEG calidad [JPEG_QUALITY] antes de devolver — no hace falta resolución completa
 * para que un modelo de visión la entienda, y una foto sin comprimir saturaría el
 * WebSocket y el contexto del modelo sin necesidad.
 *
 * CameraX pide un [LifecycleOwner] para `bindToLifecycle`; como esto corre desde
 * [PhoneLinkService] (un Service, sin ninguna Activity en foreground), se usa un
 * [LifecycleOwner] manual de un solo uso que pasa a CREATED/STARTED al bindear y a
 * DESTROYED al terminar, para soltar la cámara de una apenas se saca la foto.
 *
 * No validado contra un dispositivo real todavía (pendiente de que se instale el APK)
 * — si algo de este binding falla en la práctica, es el primer lugar a revisar.
 */
object CameraXPhoneCamera : PhoneCamera {
    private const val MAX_DIMENSION = 1024
    private const val JPEG_QUALITY = 80

    override suspend fun takePhoto(context: Context, useFrontCamera: Boolean): PhotoCaptureResult {
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            throw CameraPermissionDeniedException()
        }

        val tempFile = File.createTempFile("jarvis_photo_", ".jpg", context.cacheDir)
        try {
            captureToFile(context, tempFile, useFrontCamera)
            return resizeAndEncode(tempFile)
        } finally {
            tempFile.delete()
        }
    }

    private suspend fun getCameraProvider(context: Context): ProcessCameraProvider =
        suspendCancellableCoroutine { cont ->
            val future = ProcessCameraProvider.getInstance(context)
            future.addListener(
                { cont.resume(future.get()) },
                ContextCompat.getMainExecutor(context),
            )
        }

    /** CameraX exige que bindToLifecycle/takePicture corran en el main thread. */
    private suspend fun captureToFile(context: Context, file: File, useFrontCamera: Boolean) {
        withContext(Dispatchers.Main) {
            val cameraProvider = getCameraProvider(context)
            val lifecycleOwner = OneShotLifecycleOwner()
            val imageCapture = ImageCapture.Builder()
                .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                .build()
            val selector = if (useFrontCamera) {
                CameraSelector.DEFAULT_FRONT_CAMERA
            } else {
                CameraSelector.DEFAULT_BACK_CAMERA
            }

            try {
                lifecycleOwner.start()
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(lifecycleOwner, selector, imageCapture)

                val outputOptions = ImageCapture.OutputFileOptions.Builder(file).build()
                suspendCancellableCoroutine<Unit> { cont ->
                    imageCapture.takePicture(
                        outputOptions,
                        ContextCompat.getMainExecutor(context),
                        object : ImageCapture.OnImageSavedCallback {
                            override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                                if (cont.isActive) cont.resume(Unit)
                            }

                            override fun onError(exc: ImageCaptureException) {
                                if (cont.isActive) cont.resumeWithException(exc)
                            }
                        },
                    )
                }
            } finally {
                cameraProvider.unbindAll()
                lifecycleOwner.destroy()
            }
        }
    }

    private fun resizeAndEncode(file: File): PhotoCaptureResult {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, bounds)
        val sampleSize = calculateInSampleSize(bounds.outWidth, bounds.outHeight, MAX_DIMENSION)

        val decodeOptions = BitmapFactory.Options().apply { inSampleSize = sampleSize }
        val decoded = BitmapFactory.decodeFile(file.absolutePath, decodeOptions)
            ?: throw IllegalStateException("No se pudo decodificar la foto capturada")

        val scaled = scaleToMaxDimension(decoded, MAX_DIMENSION)
        val output = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)

        return PhotoCaptureResult(
            imageBase64 = Base64.encodeToString(output.toByteArray(), Base64.NO_WRAP),
            mimeType = "image/jpeg",
            width = scaled.width,
            height = scaled.height,
        )
    }

    private fun calculateInSampleSize(width: Int, height: Int, maxDimension: Int): Int {
        var sampleSize = 1
        val longest = max(width, height)
        while (longest / (sampleSize * 2) >= maxDimension) {
            sampleSize *= 2
        }
        return sampleSize
    }

    private fun scaleToMaxDimension(bitmap: Bitmap, maxDimension: Int): Bitmap {
        val longest = max(bitmap.width, bitmap.height)
        if (longest <= maxDimension) return bitmap
        val scale = maxDimension.toFloat() / longest
        val newWidth = (bitmap.width * scale).toInt().coerceAtLeast(1)
        val newHeight = (bitmap.height * scale).toInt().coerceAtLeast(1)
        return Bitmap.createScaledBitmap(bitmap, newWidth, newHeight, true)
    }

    private class OneShotLifecycleOwner : LifecycleOwner {
        private val registry = LifecycleRegistry(this)
        override val lifecycle: Lifecycle get() = registry

        fun start() {
            registry.currentState = Lifecycle.State.CREATED
            registry.currentState = Lifecycle.State.STARTED
        }

        fun destroy() {
            registry.currentState = Lifecycle.State.DESTROYED
        }
    }
}

/** Punto de inyección para tests: [PhoneToolHandler] usa esto en vez de la cámara real
 * directamente, para poder mockearla sin disparar CameraX de verdad. */
object PhoneCameraProvider {
    var instance: PhoneCamera = CameraXPhoneCamera
}
