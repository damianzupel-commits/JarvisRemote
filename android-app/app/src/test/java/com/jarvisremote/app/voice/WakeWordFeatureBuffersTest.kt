package com.jarvisremote.app.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

/**
 * Tests de la mecánica de buffers del pipeline de wake word con modelos falsos.
 * La equivalencia numérica contra openWakeWord real ya se validó aparte (mismo
 * audio sintético contra la implementación Python oficial: scores idénticos a 6
 * decimales tras el warmup) — acá se fija la mecánica de ventanas para que un
 * refactor no la rompa en silencio.
 */
class WakeWordFeatureBuffersTest {

    private class Capture {
        var lastRawWindow: FloatArray? = null
        var lastMelWindow: Array<FloatArray>? = null
        var lastEmbeddingWindow: Array<FloatArray>? = null
        var embeddingCallCount = 0
    }

    /** Detector con modelos falsos que capturan sus entradas y devuelven valores marcados. */
    private fun buildDetector(
        capture: Capture,
        melOut: Float = 0f,
        embeddingOut: (Int) -> FloatArray = { FloatArray(WakeWordFeatureBuffers.EMBEDDING_SIZE) },
        wakeOut: Float = 0.42f,
    ) = WakeWordFeatureBuffers(
        melModel = { raw ->
            capture.lastRawWindow = raw
            Array(WakeWordFeatureBuffers.MEL_FRAMES_PER_STEP) {
                FloatArray(WakeWordFeatureBuffers.MEL_BINS) { melOut }
            }
        },
        embeddingModel = { mel ->
            capture.lastMelWindow = mel
            capture.embeddingCallCount++
            embeddingOut(capture.embeddingCallCount)
        },
        wakeModel = { emb ->
            capture.lastEmbeddingWindow = emb
            wakeOut
        },
    )

    private fun frameOf(value: Short) = ShortArray(WakeWordFeatureBuffers.FRAME_SAMPLES) { value }

    @Test
    fun `devuelve el score del modelo de wake word`() {
        val detector = buildDetector(Capture(), wakeOut = 0.77f)
        assertEquals(0.77f, detector.processFrame(frameOf(0)), 1e-6f)
    }

    @Test
    fun `rechaza frames de tamano incorrecto`() {
        val detector = buildDetector(Capture())
        assertThrows(IllegalArgumentException::class.java) {
            detector.processFrame(ShortArray(100))
        }
    }

    @Test
    fun `la ventana cruda termina con el frame nuevo y arranca con la cola del anterior`() {
        val capture = Capture()
        val detector = buildDetector(capture)

        detector.processFrame(frameOf(100))
        detector.processFrame(frameOf(200))

        val raw = capture.lastRawWindow!!
        assertEquals(WakeWordFeatureBuffers.RAW_WINDOW, raw.size)
        // Los primeros 480 son la cola del frame anterior (todo 100s).
        assertEquals(100f, raw[0], 0f)
        assertEquals(100f, raw[479], 0f)
        // El resto es el frame nuevo (todo 200s).
        assertEquals(200f, raw[480], 0f)
        assertEquals(200f, raw[raw.size - 1], 0f)
    }

    @Test
    fun `aplica la transformacion x div 10 mas 2 a los frames de mel`() {
        val capture = Capture()
        val detector = buildDetector(capture, melOut = 30f)

        detector.processFrame(frameOf(0))

        val mel = capture.lastMelWindow!!
        assertEquals(WakeWordFeatureBuffers.MEL_WINDOW, mel.size)
        // Los últimos MEL_FRAMES_PER_STEP frames son los nuevos: 30/10 + 2 = 5.
        val newest = mel[WakeWordFeatureBuffers.MEL_WINDOW - 1]
        assertEquals(5f, newest[0], 1e-6f)
        // Los primeros siguen en cero (buffer inicial), sin transformar dos veces.
        assertEquals(0f, mel[0][0], 0f)
    }

    @Test
    fun `la ventana de embeddings rueda de a uno con el mas nuevo al final`() {
        val capture = Capture()
        // Cada embedding lleva el número de llamada, para rastrear el orden.
        val detector = buildDetector(
            capture,
            embeddingOut = { call -> FloatArray(WakeWordFeatureBuffers.EMBEDDING_SIZE) { call.toFloat() } },
        )

        repeat(3) { detector.processFrame(frameOf(0)) }

        val window = capture.lastEmbeddingWindow!!
        assertEquals(WakeWordFeatureBuffers.EMBEDDING_WINDOW, window.size)
        val last = WakeWordFeatureBuffers.EMBEDDING_WINDOW - 1
        assertEquals(3f, window[last][0], 0f) // el más nuevo al final
        assertEquals(2f, window[last - 1][0], 0f)
        assertEquals(1f, window[last - 2][0], 0f)
        assertEquals(0f, window[0][0], 0f) // el resto sigue en el cero inicial
    }

    @Test
    fun `reset limpia los buffers`() {
        val capture = Capture()
        val detector = buildDetector(
            capture,
            embeddingOut = { call -> FloatArray(WakeWordFeatureBuffers.EMBEDDING_SIZE) { call.toFloat() } },
        )

        detector.processFrame(frameOf(500))
        detector.reset()
        detector.processFrame(frameOf(0))

        val raw = capture.lastRawWindow!!
        assertEquals(0f, raw[0], 0f) // sin rastros del frame de 500s previo al reset
        val window = capture.lastEmbeddingWindow!!
        // Tras el reset, los embeddings viejos (llamada 1) fueron limpiados; solo
        // queda el de la llamada 2 al final.
        assertEquals(0f, window[WakeWordFeatureBuffers.EMBEDDING_WINDOW - 2][0], 0f)
        assertEquals(2f, window[WakeWordFeatureBuffers.EMBEDDING_WINDOW - 1][0], 0f)
    }
}
