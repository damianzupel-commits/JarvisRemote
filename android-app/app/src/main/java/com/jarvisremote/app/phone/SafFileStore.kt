package com.jarvisremote.app.phone

import android.content.Context
import android.net.Uri
import android.webkit.MimeTypeMap
import androidx.documentfile.provider.DocumentFile
import java.io.FileNotFoundException
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject

/**
 * Filesystem del celular sandboxeado al árbol SAF que el usuario eligió una vez en
 * Configuración (mismo modelo que `FS_ALLOWED_ROOT` del lado de la PC, ver
 * `backend/app/tools/filesystem.py`). No hay acceso al filesystem fuera de ese árbol:
 * cualquier segmento `..` en el path rechaza la operación.
 */
object SafFileStore {

    class NoFolderConfiguredException : Exception(
        "No hay ninguna carpeta elegida en el celular. Andá a Configuración y elegí una."
    )

    private fun segments(relativePath: String): List<String> {
        val parts = relativePath.split('/').filter { it.isNotBlank() && it != "." }
        if (parts.any { it == ".." }) {
            throw SecurityException("Path '$relativePath' intenta salir de la carpeta permitida")
        }
        return parts
    }

    private fun root(context: Context, treeUri: String): DocumentFile {
        if (treeUri.isBlank()) throw NoFolderConfiguredException()
        val doc = DocumentFile.fromTreeUri(context, Uri.parse(treeUri))
            ?: throw FileNotFoundException("No se pudo abrir la carpeta elegida")
        return doc
    }

    private fun resolveExisting(context: Context, treeUri: String, relativePath: String): DocumentFile {
        var node = root(context, treeUri)
        for (segment in segments(relativePath)) {
            node = node.findFile(segment) ?: throw FileNotFoundException("'$relativePath' no existe")
        }
        return node
    }

    /** Recorre/crea las carpetas intermedias y devuelve la carpeta padre del último segmento. */
    private fun resolveParentCreating(context: Context, treeUri: String, relativePath: String): Pair<DocumentFile, String> {
        val parts = segments(relativePath)
        if (parts.isEmpty()) throw IllegalArgumentException("Path vacío")
        var node = root(context, treeUri)
        for (segment in parts.dropLast(1)) {
            node = node.findFile(segment) ?: node.createDirectory(segment)
                ?: throw FileNotFoundException("No se pudo crear la carpeta '$segment'")
        }
        return node to parts.last()
    }

    fun listDir(context: Context, treeUri: String, relativePath: String): JsonObject {
        val dir = if (relativePath.isBlank() || relativePath == ".") {
            root(context, treeUri)
        } else {
            resolveExisting(context, treeUri, relativePath)
        }
        if (!dir.isDirectory) throw IllegalArgumentException("'$relativePath' no es una carpeta")

        val entries = buildJsonArray {
            for (child in dir.listFiles().sortedBy { it.name ?: "" }) {
                add(
                    buildJsonObject {
                        put("name", JsonPrimitive(child.name ?: ""))
                        put("type", JsonPrimitive(if (child.isDirectory) "dir" else "file"))
                        put(
                            "size_bytes",
                            if (child.isFile) JsonPrimitive(child.length()) else JsonNull,
                        )
                    },
                )
            }
        }
        return buildJsonObject {
            put("path", JsonPrimitive(relativePath.ifBlank { "." }))
            put("entries", entries)
        }
    }

    fun readFile(context: Context, treeUri: String, relativePath: String, maxChars: Int): JsonObject {
        val file = resolveExisting(context, treeUri, relativePath)
        if (!file.isFile) throw IllegalArgumentException("'$relativePath' no es un archivo")

        val text = context.contentResolver.openInputStream(file.uri)?.use { stream ->
            stream.readBytes().toString(Charsets.UTF_8)
        } ?: throw FileNotFoundException("No se pudo leer '$relativePath'")

        val truncated = text.length > maxChars
        return buildJsonObject {
            put("path", JsonPrimitive(relativePath))
            put("content", JsonPrimitive(text.take(maxChars)))
            put("truncated", JsonPrimitive(truncated))
        }
    }

    fun writeFile(context: Context, treeUri: String, relativePath: String, content: String, append: Boolean): JsonObject {
        val (parent, name) = resolveParentCreating(context, treeUri, relativePath)
        val existing = parent.findFile(name)
        val target = existing ?: parent.createFile(mimeTypeFor(name), name)
            ?: throw FileNotFoundException("No se pudo crear '$relativePath'")

        val mode = if (append) "wa" else "wt"
        context.contentResolver.openOutputStream(target.uri, mode)?.use { stream ->
            stream.write(content.toByteArray(Charsets.UTF_8))
        } ?: throw FileNotFoundException("No se pudo escribir '$relativePath'")

        return buildJsonObject {
            put("path", JsonPrimitive(relativePath))
            put("bytes_written", JsonPrimitive(content.toByteArray(Charsets.UTF_8).size))
            put("append", JsonPrimitive(append))
        }
    }

    private fun mimeTypeFor(fileName: String): String {
        val ext = fileName.substringAfterLast('.', "")
        if (ext.isBlank()) return "application/octet-stream"
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(ext.lowercase())
            ?: "application/octet-stream"
    }
}
