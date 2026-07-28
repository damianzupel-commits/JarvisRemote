package com.jarvisremote.app.voice

import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import java.io.File
import java.io.RandomAccessFile
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * Graba muestras de audio real (16kHz mono PCM, WAV) para cerrar la brecha
 * sintético-vs-real del modelo de wake word: el modelo entrenado solo con TTS dio
 * ~0.999 de recall offline pero prácticamente no reaccionó a la voz real de Damian
 * en la prueba de campo (scores <0.15 con amplitud de audio real alta) -- hace
 * falta reentrenar mezclando estas grabaciones reales con el dataset sintético.
 *
 * Deliberadamente separado de [VoiceListenerService] (que corre el modelo, no
 * graba crudo) -- esto es una herramienta de una sola vez para juntar dataset,
 * no una feature permanente. Guarda en getExternalFilesDir() (visible por
 * `adb pull` sin necesidad de root ni `run-as`).
 */
class SampleRecorder(private val context: Context) {
    companion object {
        private const val SAMPLE_RATE = 16000
    }

    private var audioRecord: AudioRecord? = null
    private var recordingThread: Thread? = null
    @Volatile private var stopRequested = false
    private var currentFile: File? = null

    val isRecording: Boolean
        get() = audioRecord != null

    fun outputDir(): File {
        val dir = File(context.getExternalFilesDir(null), "training_samples")
        dir.mkdirs()
        return dir
    }

    /** Arranca a grabar en un hilo aparte; el archivo queda con el header WAV recién al llamar [stop]. */
    fun start(label: String) {
        if (isRecording) return
        val minBuffer = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
        )
        val record = AudioRecord(
            MediaRecorder.AudioSource.MIC, SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT,
            maxOf(minBuffer, 8192),
        )
        if (record.state != AudioRecord.STATE_INITIALIZED) {
            record.release()
            throw IllegalStateException("No se pudo inicializar el micrófono")
        }

        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val file = File(outputDir(), "${label}_$timestamp.wav")
        currentFile = file
        audioRecord = record
        stopRequested = false

        // 44 bytes de header WAV placeholder -- se rellena de verdad en stop(),
        // cuando ya se sabe el tamaño total de los datos grabados.
        file.writeBytes(ByteArray(44))

        record.startRecording()
        recordingThread = Thread {
            val buffer = ShortArray(2048)
            RandomAccessFile(file, "rw").use { raf ->
                raf.seek(44)
                while (!stopRequested) {
                    val read = record.read(buffer, 0, buffer.size)
                    if (read > 0) {
                        val bytes = ByteArray(read * 2)
                        for (i in 0 until read) {
                            val v = buffer[i].toInt()
                            bytes[i * 2] = (v and 0xFF).toByte()
                            bytes[i * 2 + 1] = ((v shr 8) and 0xFF).toByte()
                        }
                        raf.write(bytes)
                    }
                }
            }
        }.also { it.start() }
    }

    /** Para la grabación, espera a que el hilo termine de volcar el buffer, y escribe el header WAV final. */
    suspend fun stop(): File? = withContext(Dispatchers.IO) {
        val record = audioRecord ?: return@withContext null
        stopRequested = true
        record.stop()
        recordingThread?.join(2000)
        record.release()
        audioRecord = null
        recordingThread = null

        val file = currentFile ?: return@withContext null
        writeWavHeader(file)
        file
    }

    private fun writeWavHeader(file: File) {
        val dataSize = file.length() - 44
        val byteRate = SAMPLE_RATE * 2
        RandomAccessFile(file, "rw").use { raf ->
            raf.seek(0)
            raf.write("RIFF".toByteArray())
            raf.write(intLE((dataSize + 36).toInt()))
            raf.write("WAVE".toByteArray())
            raf.write("fmt ".toByteArray())
            raf.write(intLE(16))
            raf.write(shortLE(1)) // PCM
            raf.write(shortLE(1)) // mono
            raf.write(intLE(SAMPLE_RATE))
            raf.write(intLE(byteRate))
            raf.write(shortLE(2)) // block align
            raf.write(shortLE(16)) // bits per sample
            raf.write("data".toByteArray())
            raf.write(intLE(dataSize.toInt()))
        }
    }

    private fun intLE(v: Int): ByteArray = byteArrayOf(
        (v and 0xFF).toByte(), ((v shr 8) and 0xFF).toByte(),
        ((v shr 16) and 0xFF).toByte(), ((v shr 24) and 0xFF).toByte(),
    )

    private fun shortLE(v: Int): ByteArray = byteArrayOf((v and 0xFF).toByte(), ((v shr 8) and 0xFF).toByte())
}
