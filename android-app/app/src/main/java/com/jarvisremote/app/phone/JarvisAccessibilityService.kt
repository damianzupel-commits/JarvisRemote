package com.jarvisremote.app.phone

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import com.jarvisremote.app.data.SettingsRepository
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject

/**
 * Control genérico de pantalla del celular: tap/swipe/type/read/global-action sobre
 * cualquier app visible, vía el Accessibility Service. El usuario tiene que habilitarlo
 * a mano en Ajustes → Accesibilidad (no se puede activar programáticamente); ver
 * `SettingsScreen` para el link directo.
 *
 * Riesgo asumido explícitamente por el usuario: este servicio puede leer y accionar
 * sobre cualquier app en pantalla, incluidas apps de banca, 2FA, mensajería, etc.
 *
 * Mitigación parcial: cada acción chequea la app en foreground contra un blocklist
 * configurable (`SettingsRepository.blockedPackages`, ver `AccessibilityBlocklist.kt`)
 * y se niega si matchea — por nombre de paquete exacto, no un sandbox real. Viene
 * con una lista default de apps de 2FA conocidas; agregar bancos específicos desde
 * Ajustes.
 */
class JarvisAccessibilityService : AccessibilityService() {

    // Nested afuera del companion object a propósito: una clase declarada
    // adentro de un companion object solo se resuelve como
    // `Outer.Companion.NotEnabledException`, no como `Outer.NotEnabledException`
    // (a diferencia de properties/funciones, que sí se promueven). Acá afuera
    // sí resuelve como espera `PhoneToolHandler`.
    class NotEnabledException : Exception(
        "El Accessibility Service de Jarvis no está habilitado en este celular."
    )

    companion object {
        @Volatile
        var instance: JarvisAccessibilityService? = null
            private set

        private const val GESTURE_TIMEOUT_MS = 5_000L
        private const val MAX_NODES = 400
        private const val MAX_DEPTH = 40
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    override fun onUnbind(intent: android.content.Intent?): Boolean {
        if (instance === this) instance = null
        return super.onUnbind(intent)
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // No necesitamos stream de eventos: las tools leen rootInActiveWindow bajo demanda.
    }

    override fun onInterrupt() {}

    /**
     * Chequea la app en foreground contra el blocklist configurable (ver
     * `AccessibilityBlocklist.kt` / `SettingsRepository.blockedPackages`) y tira
     * [SensitiveAppBlockedException] si está bloqueada. Se llama al principio de
     * cada acción — mitigación por nombre de paquete, no una garantía completa
     * (ver el docstring de `isForegroundAppBlocked`).
     */
    private suspend fun assertForegroundAppNotBlocked() {
        val blockedPackages = SettingsRepository(applicationContext).settingsFlow.first().blockedPackages
        val currentPackage = rootInActiveWindow?.packageName?.toString()
        if (isForegroundAppBlocked(currentPackage, blockedPackages)) {
            throw SensitiveAppBlockedException(currentPackage!!)
        }
    }

    suspend fun tap(x: Int, y: Int) {
        assertForegroundAppNotBlocked()
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val stroke = GestureDescription.StrokeDescription(path, 0, 50)
        dispatchGestureAwait(GestureDescription.Builder().addStroke(stroke).build())
    }

    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int) {
        assertForegroundAppNotBlocked()
        val path = Path().apply {
            moveTo(x1.toFloat(), y1.toFloat())
            lineTo(x2.toFloat(), y2.toFloat())
        }
        val stroke = GestureDescription.StrokeDescription(path, 0, durationMs.toLong().coerceAtLeast(1))
        dispatchGestureAwait(GestureDescription.Builder().addStroke(stroke).build())
    }

    private suspend fun dispatchGestureAwait(gesture: GestureDescription) {
        withTimeout(GESTURE_TIMEOUT_MS) {
            suspendCancellableCoroutine<Unit> { cont ->
                val callback = object : GestureResultCallback() {
                    override fun onCompleted(gestureDescription: GestureDescription?) {
                        if (cont.isActive) cont.resume(Unit)
                    }

                    override fun onCancelled(gestureDescription: GestureDescription?) {
                        if (cont.isActive) {
                            cont.resumeWithException(RuntimeException("El gesto fue cancelado por el sistema"))
                        }
                    }
                }
                val dispatched = dispatchGesture(gesture, callback, null)
                if (!dispatched && cont.isActive) {
                    cont.resumeWithException(RuntimeException("No se pudo iniciar el gesto"))
                }
            }
        }
    }

    suspend fun typeText(text: String) {
        assertForegroundAppNotBlocked()
        val focused = rootInActiveWindow?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
            ?: throw IllegalStateException(
                "No hay ningún campo de texto enfocado. Usá phone_tap para enfocarlo primero."
            )
        val arguments = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        val ok = focused.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, arguments)
        if (!ok) throw RuntimeException("El campo enfocado rechazó el texto")
    }

    suspend fun globalAction(action: String) {
        assertForegroundAppNotBlocked()
        val code = when (action) {
            "back" -> GLOBAL_ACTION_BACK
            "home" -> GLOBAL_ACTION_HOME
            "recents" -> GLOBAL_ACTION_RECENTS
            "notifications" -> GLOBAL_ACTION_NOTIFICATIONS
            else -> throw IllegalArgumentException("Acción global desconocida: '$action'")
        }
        if (!performGlobalAction(code)) {
            throw RuntimeException("El sistema rechazó la acción global '$action'")
        }
    }

    suspend fun readScreen(): kotlinx.serialization.json.JsonObject {
        assertForegroundAppNotBlocked()
        val root = rootInActiveWindow
            ?: return buildJsonObject { put("nodes", buildJsonArray {}) }
        val nodes = buildJsonArray {
            var visited = 0
            fun walk(node: AccessibilityNodeInfo, depth: Int) {
                if (visited >= MAX_NODES || depth > MAX_DEPTH) return
                visited++
                val bounds = Rect().also { node.getBoundsInScreen(it) }
                add(
                    buildJsonObject {
                        put("class_name", JsonPrimitive(node.className?.toString() ?: ""))
                        put("text", JsonPrimitive(node.text?.toString() ?: ""))
                        put("content_description", JsonPrimitive(node.contentDescription?.toString() ?: ""))
                        put("clickable", JsonPrimitive(node.isClickable))
                        put("editable", JsonPrimitive(node.isEditable))
                        put("focused", JsonPrimitive(node.isFocused))
                        put(
                            "bounds",
                            buildJsonObject {
                                put("left", JsonPrimitive(bounds.left))
                                put("top", JsonPrimitive(bounds.top))
                                put("right", JsonPrimitive(bounds.right))
                                put("bottom", JsonPrimitive(bounds.bottom))
                            },
                        )
                    },
                )
                for (i in 0 until node.childCount) {
                    if (visited >= MAX_NODES) break
                    node.getChild(i)?.let { walk(it, depth + 1) }
                }
            }
            walk(root, 0)
        }
        return buildJsonObject { put("nodes", nodes) }
    }
}
