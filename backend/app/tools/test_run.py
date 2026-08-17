"""Tool `code_run_tests` -- el paso de 'testear real' del pipeline de
auditoría (crear -> auditar -> corregir -> TESTEAR -> re-auditar). Ver
`app/testing/runner.py` para la lógica real; acá solo se expone al LLM y se
audita.

Pensado para llamarse DESPUÉS de aplicar un fix (con `code_apply_fix` o a
mano) y ANTES de dar por cerrado un ciclo de auditoría -- `security_scan_project`
puede confirmar que un patrón de código ya no matchea, pero solo una corrida
de tests real confirma que el proyecto sigue FUNCIONANDO. `security_audit_find_fix_verify`
(el flujo atómico apply+commit+verify) ya llama a esto automáticamente después
de cada fix; este tool es para el resto de los casos -- correrlo a mano, o
como parte del flujo con revisión humana (code_apply_fix)."""

from __future__ import annotations

from .. import audit_log
from ..testing.runner import run_tests
from . import register_tool


@register_tool(
    name="code_run_tests",
    description=(
        "Detecta y corre la suite de tests REAL de un proyecto (pytest si hay archivos test_*.py/*_test.py/carpeta "
        "tests detectados por el índice de Codebase -- no hace falta ningún pytest.ini/pyproject.toml, pytest los "
        "descubre igual, 'npm test' si package.json trae un script 'test' real, 'gradlew test' si hay wrapper de "
        "Gradle, 'go test ./...' si hay go.mod, 'cargo test' si hay Cargo.toml) -- mismo mecanismo de ejecución "
        "que pc_run_command (timeout duro, mata el proceso si se cuelga). Usar "
        "DESPUÉS de aplicar un fix (code_apply_fix o security_audit_find_fix_verify) y ANTES de considerar el "
        "ciclo de auditoría cerrado: que un hallazgo de security_scan_project/quality_scan_project ya no aparezca "
        "no confirma que el proyecto sigue funcionando, solo una corrida de tests real lo hace. El resultado "
        "queda guardado como 'última corrida de tests' del proyecto -- audit_generate_report lo lee y lo marca "
        "explícitamente en el reporte, así 'compiló' nunca se confunde con 'está verificado'. Si no se detecta "
        "ningún comando de test real (proyecto sin suite, o sin ninguno de los marcadores soportados), "
        "'detected' viene en false -- no es un fallo del proyecto, es que no hay nada que correr; decíselo así "
        "al usuario, no lo reportes como que los tests fallaron."
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Ruta absoluta a la raíz del proyecto (ya indexado con codebase_index_project, o se indexa ahora)."},
            "timeout": {
                "type": "integer",
                "description": "Segundos a esperar antes de matar la corrida (default 300, tope duro 600 sin importar lo que se pida).",
            },
        },
        "required": ["path"],
    },
)
def code_run_tests(path: str, timeout: float = 300.0) -> dict:
    arguments = {"path": path, "timeout": timeout}
    try:
        result = run_tests(path, timeout=timeout)
    except Exception as exc:
        audit_log.log_tool_call(target="code", tool="code_run_tests", arguments=arguments, error=str(exc))
        raise
    audit_log.log_tool_call(target="code", tool="code_run_tests", arguments=arguments, result=result.to_dict())
    return result.to_dict()
