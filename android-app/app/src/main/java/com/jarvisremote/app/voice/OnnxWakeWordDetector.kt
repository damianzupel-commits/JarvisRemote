package com.jarvisremote.app.voice

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import java.nio.FloatBuffer

/**
 * Detector de "hey Jarvis" on-device: carga los tres modelos ONNX de openWakeWord
 * (Apache-2.0, empaquetados en assets/openwakeword/) y los encadena con la lógica
 * de buffers de [WakeWordFeatureBuffers].
 *
 * Port propio sobre ONNX Runtime (sin TFLite) del pipeline de openWakeWord — la
 * alternativa (vendorear el port comunitario openWakeWord-Android tal cual) traía
 * dos runtimes de inferencia, codegen de TFLite y un modelo verificador específico
 * de "alexa" que no aplica acá. La mecánica de buffers es la misma y está validada
 * contra la implementación oficial de Python (ver docstring de WakeWordFeatureBuffers).
 *
 * No es thread-safe: usarlo siempre desde el mismo hilo/coroutine del loop de audio.
 */
class OnnxWakeWordDetector(context: Context) : AutoCloseable {

    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val melSession: OrtSession
    private val embeddingSession: OrtSession
    private val wakeSession: OrtSession

    private val buffers: WakeWordFeatureBuffers

    init {
        val assets = context.assets
        melSession = env.createSession(assets.open("openwakeword/melspectrogram.onnx").readBytes())
        embeddingSession = env.createSession(assets.open("openwakeword/embedding_model.onnx").readBytes())
        wakeSession = env.createSession(assets.open("openwakeword/hey_jarvis_v0.1.onnx").readBytes())

        buffers = WakeWordFeatureBuffers(
            melModel = ::runMel,
            embeddingModel = ::runEmbedding,
            wakeModel = ::runWake,
        )
    }

    /** Procesa 1280 muestras PCM16 (80 ms) y devuelve el score 0..1 de "hey jarvis". */
    fun processFrame(pcm: ShortArray): Float = buffers.processFrame(pcm)

    fun reset() = buffers.reset()

    override fun close() {
        melSession.close()
        embeddingSession.close()
        wakeSession.close()
    }

    // ------------------------------------------------------------------ modelos

    /** [1, 1760] float -> (1, 1, 8, 32); devuelve los 8 frames de mel sin transformar. */
    private fun runMel(rawWindow: FloatArray): Array<FloatArray> {
        OnnxTensor.createTensor(env, FloatBuffer.wrap(rawWindow), longArrayOf(1, rawWindow.size.toLong())).use { input ->
            melSession.run(mapOf("input" to input)).use { result ->
                @Suppress("UNCHECKED_CAST")
                val out = result[0].value as Array<Array<Array<FloatArray>>> // (1, 1, 8, 32)
                return out[0][0]
            }
        }
    }

    /** [1, 76, 32, 1] float -> (1, 1, 1, 96); devuelve el embedding plano de 96. */
    private fun runEmbedding(melWindow: Array<FloatArray>): FloatArray {
        val flat = FloatArray(WakeWordFeatureBuffers.MEL_WINDOW * WakeWordFeatureBuffers.MEL_BINS)
        var idx = 0
        for (frame in melWindow) {
            for (v in frame) flat[idx++] = v
        }
        val shape = longArrayOf(1, WakeWordFeatureBuffers.MEL_WINDOW.toLong(), WakeWordFeatureBuffers.MEL_BINS.toLong(), 1)
        OnnxTensor.createTensor(env, FloatBuffer.wrap(flat), shape).use { input ->
            embeddingSession.run(mapOf("input_1" to input)).use { result ->
                @Suppress("UNCHECKED_CAST")
                val out = result[0].value as Array<Array<Array<FloatArray>>> // (1, 1, 1, 96)
                return out[0][0][0]
            }
        }
    }

    /** [1, 16, 96] float -> (1, 1); devuelve el score escalar. */
    private fun runWake(embeddingWindow: Array<FloatArray>): Float {
        val flat = FloatArray(WakeWordFeatureBuffers.EMBEDDING_WINDOW * WakeWordFeatureBuffers.EMBEDDING_SIZE)
        var idx = 0
        for (emb in embeddingWindow) {
            for (v in emb) flat[idx++] = v
        }
        val shape = longArrayOf(1, WakeWordFeatureBuffers.EMBEDDING_WINDOW.toLong(), WakeWordFeatureBuffers.EMBEDDING_SIZE.toLong())
        OnnxTensor.createTensor(env, FloatBuffer.wrap(flat), shape).use { input ->
            wakeSession.run(mapOf("x.1" to input)).use { result ->
                @Suppress("UNCHECKED_CAST")
                val out = result[0].value as Array<FloatArray> // (1, 1)
                return out[0][0]
            }
        }
    }
}
