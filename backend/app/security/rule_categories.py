"""Mapeo `rule_id` de Semgrep -> categoría de OWASP Benchmark (11 categorías,
cada una con exactamente 1 CWE) -- construido a mano leyendo los `check_id`
reales que aparecieron corriendo `--config auto` contra el corpus completo de
OWASP Benchmark (ver `docs/owasp_benchmark/`), no copiado de documentación de
Semgrep.

Ámbito real: cubre las 15 reglas que efectivamente aparecieron en esa corrida
-- no es un clasificador general de "cualquier rule_id de cualquier escáner a
cualquier categoría". Para un rule_id que no está acá, `CHECK_ID_TO_CATEGORY.get(...)`
devuelve `None` -- eso es correcto y esperado, no un bug: significa que no
sabemos la categoría OWASP Benchmark de ese hallazgo puntual, así que no
corresponde inventarle una.

Extraído a un módulo propio 2026-08-11 porque `app/security/triage.py`
necesita esta misma correspondencia para el lookup determinístico de la
referencia curada por categoría (ver `triage_reference.py`) -- ya estaba
duplicado a mano en `docs/owasp_benchmark/score_semgrep_results.py` y en
`docs/owasp_benchmark/run_triage_benchmark.py`; agregarlo una tercera vez acá
adentro habría sido la señal de que ya no debía seguir copy-pasteado. Los dos
scripts de benchmark siguen con su propia copia (viven fuera de `app/`, no
importan del backend) -- si en algún momento hay que tocar el mapeo, hay que
actualizar las tres."""

from __future__ import annotations

CHECK_ID_TO_CATEGORY: dict[str, str] = {
    "java.lang.security.audit.xss.no-direct-response-writer.no-direct-response-writer": "xss",
    "java.lang.security.audit.sqli.tainted-sql-from-http-request.tainted-sql-from-http-request": "sqli",
    "java.lang.security.httpservlet-path-traversal.httpservlet-path-traversal": "pathtraver",
    "java.lang.security.audit.tainted-cmd-from-http-request.tainted-cmd-from-http-request": "cmdi",
    "java.lang.security.audit.crypto.weak-random.weak-random": "weakrand",
    "java.lang.security.audit.sqli.jdbc-sqli.jdbc-sqli": "sqli",
    "java.lang.security.audit.crypto.des-is-deprecated.des-is-deprecated": "crypto",
    "java.lang.security.audit.crypto.desede-is-deprecated.desede-is-deprecated": "crypto",
    "java.lang.security.audit.crypto.use-of-sha1.use-of-sha1": "hash",
    "java.lang.security.audit.command-injection-process-builder.command-injection-process-builder": "cmdi",
    "java.lang.security.audit.tainted-session-from-http-request.tainted-session-from-http-request": "trustbound",
    "java.lang.security.audit.tainted-ldapi-from-http-request.tainted-ldapi-from-http-request": "ldapi",
    "java.lang.security.audit.cookie-missing-secure-flag.cookie-missing-secure-flag": "securecookie",
    "java.lang.security.audit.crypto.use-of-md5.use-of-md5": "hash",
    "java.lang.security.audit.tainted-xpath-from-http-request.tainted-xpath-from-http-request": "xpathi",
}

CATEGORY_LABEL: dict[str, str] = {
    "sqli": "SQL Injection",
    "weakrand": "Weak Random Number",
    "xss": "Cross-Site Scripting",
    "pathtraver": "Path Traversal",
    "cmdi": "Command Injection",
    "crypto": "Weak Encryption Algorithm",
    "hash": "Weak Hash Algorithm",
    "trustbound": "Trust Boundary Violation",
    "securecookie": "Insecure Cookie",
    "ldapi": "LDAP Injection",
    "xpathi": "XPath Injection",
}


def category_for_rule(rule_id: str) -> str | None:
    return CHECK_ID_TO_CATEGORY.get(rule_id)
