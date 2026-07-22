package com.jarvisremote.app.phone

import android.content.Context
import android.content.Intent
import com.jarvisremote.app.data.SettingsRepository
import kotlinx.coroutines.flow.first
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull

/**
 * Router de tools con `target="phone"` (ver `backend/app/tools/phone.py` para la
 * contraparte del lado del backend, que define el schema que ve el LLM).
 */
object PhoneToolHandler {

    private fun JsonObject.reqString(name: String): String =
        (this[name] as? JsonPrimitive)?.contentOrNull
            ?: throw IllegalArgumentException("Falta el argumento '$name'")

    private fun JsonObject.optString(name: String, default: String): String =
        (this[name] as? JsonPrimitive)?.contentOrNull ?: default

    private fun JsonObject.reqInt(name: String): Int =
        (this[name] as? JsonPrimitive)?.intOrNull
            ?: throw IllegalArgumentException("Falta el argumento numérico '$name'")

    private fun JsonObject.optInt(name: String, default: Int): Int =
        (this[name] as? JsonPrimitive)?.intOrNull ?: default

    private fun JsonObject.optBoolean(name: String, default: Boolean): Boolean =
        (this[name] as? JsonPrimitive)?.booleanOrNull ?: default

    suspend fun handle(context: Context, tool: String, arguments: JsonObject): JsonElement {
        val settingsRepository = SettingsRepository(context)

        return when (tool) {
            "phone_open_app" -> openApp(context, arguments.reqString("package_name"))

            "phone_list_dir" -> {
                val folderUri = settingsRepository.settingsFlow.first().phoneFolderUri
                SafFileStore.listDir(context, folderUri, arguments.optString("path", "."))
            }

            "phone_read_file" -> {
                val folderUri = settingsRepository.settingsFlow.first().phoneFolderUri
                SafFileStore.readFile(
                    context,
                    folderUri,
                    arguments.reqString("path"),
                    arguments.optInt("max_chars", 20_000),
                )
            }

            "phone_write_file" -> {
                val folderUri = settingsRepository.settingsFlow.first().phoneFolderUri
                SafFileStore.writeFile(
                    context,
                    folderUri,
                    arguments.reqString("path"),
                    arguments.reqString("content"),
                    arguments.optBoolean("append", false),
                )
            }

            "phone_tap" -> {
                accessibility().tap(arguments.reqInt("x"), arguments.reqInt("y"))
                buildJsonObject { put("tapped", JsonPrimitive(true)) }
            }

            "phone_swipe" -> {
                accessibility().swipe(
                    arguments.reqInt("x1"),
                    arguments.reqInt("y1"),
                    arguments.reqInt("x2"),
                    arguments.reqInt("y2"),
                    arguments.optInt("duration_ms", 300),
                )
                buildJsonObject { put("swiped", JsonPrimitive(true)) }
            }

            "phone_type_text" -> {
                accessibility().typeText(arguments.reqString("text"))
                buildJsonObject { put("typed", JsonPrimitive(true)) }
            }

            "phone_read_screen" -> accessibility().readScreen()

            "phone_global_action" -> {
                accessibility().globalAction(arguments.reqString("action"))
                buildJsonObject { put("action_performed", JsonPrimitive(true)) }
            }

            "phone_run_command" -> TermuxCommandRunner.run(
                context,
                arguments.reqString("command"),
                arguments.optInt("timeout", 30) * 1000L,
            )

            "phone_take_photo" -> PhoneCameraProvider.instance
                .takePhoto(context, isFrontCameraRequested(arguments))
                .toJson()

            else -> throw IllegalArgumentException("Tool de celular desconocida: '$tool'")
        }
    }

    private fun accessibility(): JarvisAccessibilityService =
        JarvisAccessibilityService.instance
            ?: throw JarvisAccessibilityService.NotEnabledException()

    private fun openApp(context: Context, packageName: String): JsonElement {
        val intent = context.packageManager.getLaunchIntentForPackage(packageName)
            ?: throw IllegalArgumentException("No hay ninguna app instalada con package '$packageName'")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
        return buildJsonObject {
            put("launched", JsonPrimitive(true))
            put("package_name", JsonPrimitive(packageName))
        }
    }
}
