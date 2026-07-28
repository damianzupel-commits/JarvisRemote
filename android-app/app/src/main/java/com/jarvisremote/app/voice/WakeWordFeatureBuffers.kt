package com.jarvisremote.app.voice

/**
 * Lógica de buffers rodantes del pipeline de openWakeWord, separada de los modelos
 * para poder testearla en JVM puro (los modelos se inyectan como funciones; en
 * producción los provee [OnnxWakeWordDetector] con ONNX Runtime).
 *
 * Pipeline (port del `AudioFeatures` de openWakeWord, validado numéricamente contra
 * la implementación oficial de Python — los scores coinciden a 6 decimales tras el
 * warmup inicial):
 *
 *   1. Cada frame nuevo de audio son 1280 muestras PCM16 (80 ms a 16 kHz), que se
 *      usan como float SIN normalizar (el modelo de melspectrogram espera la escala
 *      cruda de int16 — normalizar a [-1, 1] acá rompe todo silenciosamente).
 *   2. Ventana cruda de 1760 muestras = 480 viejas + 1280 nuevas -> modelo de
 *      melspectrogram -> 8 frames nuevos de mel (32 bins), transformados x/10 + 2.
 *   3. Ventana de mel de 76 frames (rueda de a 8) -> modelo de embeddings -> vector
 *      de 96 floats.
 *   4. Ventana de 16 embeddings (rueda de a 1) -> modelo de wake word -> score 0..1.
 */
class WakeWordFeatureBuffers(
    /** Recibe la ventana cruda de [RAW_WINDOW] muestras; devuelve [MEL_FRAMES_PER_STEP] frames de 32 bins (sin transformar). */
    private val melModel: (FloatArray) -> Array<FloatArray>,
    /** Recibe la ventana de mel de [MEL_WINDOW] frames x 32 bins; devuelve un embedding de [EMBEDDING_SIZE] floats. */
    private val embeddingModel: (Array<FloatArray>) -> FloatArray,
    /** Recibe la ventana de [EMBEDDING_WINDOW] embeddings; devuelve el score 0..1. */
    private val wakeModel: (Array<FloatArray>) -> Float,
) {
    companion object {
        const val FRAME_SAMPLES = 1280
        const val RAW_WINDOW = 1760
        const val MEL_BINS = 32
        const val MEL_WINDOW = 76
        const val MEL_FRAMES_PER_STEP = 8
        const val EMBEDDING_SIZE = 96
        const val EMBEDDING_WINDOW = 16
    }

    private val rawWindow = FloatArray(RAW_WINDOW)
    private val melWindow = Array(MEL_WINDOW) { FloatArray(MEL_BINS) }
    private val embeddingWindow = Array(EMBEDDING_WINDOW) { FloatArray(EMBEDDING_SIZE) }

    /** Procesa un frame de 1280 muestras PCM16 y devuelve el score de wake word. */
    fun processFrame(pcm: ShortArray): Float {
        require(pcm.size == FRAME_SAMPLES) { "se esperan $FRAME_SAMPLES muestras, llegaron ${pcm.size}" }

        // 1+2: rodar la ventana cruda y computar los frames nuevos de mel.
        System.arraycopy(rawWindow, FRAME_SAMPLES, rawWindow, 0, RAW_WINDOW - FRAME_SAMPLES)
        for (i in 0 until FRAME_SAMPLES) {
            rawWindow[RAW_WINDOW - FRAME_SAMPLES + i] = pcm[i].toFloat()
        }
        val newMel = melModel(rawWindow.copyOf())

        // Rodar la ventana de mel de a MEL_FRAMES_PER_STEP y transformar (x/10 + 2).
        for (i in 0 until MEL_WINDOW - MEL_FRAMES_PER_STEP) {
            System.arraycopy(melWindow[i + MEL_FRAMES_PER_STEP], 0, melWindow[i], 0, MEL_BINS)
        }
        for (i in 0 until MEL_FRAMES_PER_STEP) {
            for (j in 0 until MEL_BINS) {
                melWindow[MEL_WINDOW - MEL_FRAMES_PER_STEP + i][j] = newMel[i][j] / 10f + 2f
            }
        }

        // 3: nuevo embedding a partir de la ventana de mel completa.
        val newEmbedding = embeddingModel(Array(MEL_WINDOW) { melWindow[it].copyOf() })

        // Rodar la ventana de embeddings de a 1.
        for (i in 0 until EMBEDDING_WINDOW - 1) {
            System.arraycopy(embeddingWindow[i + 1], 0, embeddingWindow[i], 0, EMBEDDING_SIZE)
        }
        System.arraycopy(newEmbedding, 0, embeddingWindow[EMBEDDING_WINDOW - 1], 0, EMBEDDING_SIZE)

        // 4: score final.
        return wakeModel(Array(EMBEDDING_WINDOW) { embeddingWindow[it].copyOf() })
    }

    /** Limpia todos los buffers (usar tras una detección para no re-disparar con el eco). */
    fun reset() {
        rawWindow.fill(0f)
        for (row in melWindow) row.fill(0f)
        for (row in embeddingWindow) row.fill(0f)
    }
}
