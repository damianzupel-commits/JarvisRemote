package com.jarvisremote.app.data

import java.io.IOException
import retrofit2.HttpException

fun describeError(error: Throwable): String = when (error) {
    is HttpException -> when (error.code()) {
        401 -> "API key inválida. Revisá la configuración."
        else -> "Error del backend (HTTP ${error.code()})."
    }
    is IOException -> "No se pudo conectar al backend. ¿Estás conectado a Tailscale y el backend está corriendo?"
    else -> error.message ?: "Error desconocido."
}
