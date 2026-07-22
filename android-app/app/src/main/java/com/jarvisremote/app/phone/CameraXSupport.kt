package com.jarvisremote.app.phone

import android.content.Context
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Piezas chicas compartidas entre captura de foto ([CameraXPhoneCamera]) y de video
 * ([CameraXPhoneVideoRecorder]) vía CameraX.
 */
internal suspend fun getCameraProvider(context: Context): ProcessCameraProvider =
    suspendCancellableCoroutine { cont ->
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener(
            { cont.resume(future.get()) },
            ContextCompat.getMainExecutor(context),
        )
    }

/**
 * [LifecycleOwner] manual de un solo uso: CameraX exige uno para `bindToLifecycle`, pero
 * la captura corre desde [PhoneLinkService] (un Service, sin ninguna Activity en
 * foreground) — pasa a CREATED/STARTED al bindear y a DESTROYED al terminar, para
 * soltar la cámara de una apenas se termina la captura.
 */
internal class OneShotLifecycleOwner : LifecycleOwner {
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
