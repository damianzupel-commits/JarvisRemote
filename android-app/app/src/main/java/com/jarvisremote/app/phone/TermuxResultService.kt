package com.jarvisremote.app.phone

import android.app.Service
import android.content.Intent
import android.os.IBinder
import android.util.Log

/**
 * Servicio liviano cuyo único propósito es recibir, vía `PendingIntent`, el resultado
 * asincrónico de un comando RUN_COMMAND corrido en Termux (ver [TermuxCommandRunner]).
 * No hace nada más: parsea el intent y se lo pasa a `TermuxCommandRunner.deliverResult`,
 * que resuelve la corrutina que estaba esperando ese resultado.
 */
class TermuxResultService : Service() {

    companion object {
        private const val TAG = "TermuxResultService"
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent != null) {
            TermuxCommandRunner.deliverResult(intent)
        } else {
            Log.w(TAG, "onStartCommand llamado sin intent")
        }
        stopSelf(startId)
        return START_NOT_STICKY
    }
}
