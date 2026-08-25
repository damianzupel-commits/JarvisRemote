package com.jarvisremote.app.phone

import org.junit.Assert.assertTrue
import org.junit.Test

class BlocklistAuditLogTest {

    @Test
    fun `formatea una linea de bloqueo con todos los campos`() {
        val line = BlocklistAuditLog.formatAuditLine(
            timestampMillis = 0L,
            outcome = BlocklistAuditLog.Outcome.BLOCKED_NEEDS_CONFIRMATION,
            action = "tap",
            reason = BlockReason.PATTERN_MATCH,
            packageName = "com.whatsapp",
        )

        val fields = line.split("\t")
        assertTrue("Debe tener 5 campos separados por tab", fields.size == 5)
        assertTrue(line.contains("BLOCKED_NEEDS_CONFIRMATION"))
        assertTrue(line.contains("tap"))
        assertTrue(line.contains("PATTERN_MATCH"))
        assertTrue(line.contains("pkg=com.whatsapp"))
    }

    @Test
    fun `representa el foreground desconocido de forma explicita`() {
        val line = BlocklistAuditLog.formatAuditLine(
            timestampMillis = 0L,
            outcome = BlocklistAuditLog.Outcome.BLOCKED_NEEDS_CONFIRMATION,
            action = "read_screen",
            reason = BlockReason.UNKNOWN_FOREGROUND,
            packageName = null,
        )

        assertTrue(line.contains("pkg=<desconocido>"))
        assertTrue(line.contains("UNKNOWN_FOREGROUND"))
    }

    @Test
    fun `registra la ejecucion forzada bajo confirmacion`() {
        val line = BlocklistAuditLog.formatAuditLine(
            timestampMillis = 0L,
            outcome = BlocklistAuditLog.Outcome.ALLOWED_WITH_CONFIRMATION,
            action = "phone_run_command",
            reason = BlockReason.PATTERN_MATCH,
            packageName = "rm -rf algo",
        )

        assertTrue(line.contains("ALLOWED_WITH_CONFIRMATION"))
    }
}
