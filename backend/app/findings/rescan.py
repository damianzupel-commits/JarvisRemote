"""Re-escaneo acotado a un solo archivo -- se usa después de aplicar un fix
puntual (`code_apply_fix`) para no pagar el costo de un escaneo de proyecto
completo (Semgrep con `--config auto` puede tardar minutos) solo para ver si
ESE archivo sigue teniendo hallazgos.

Compartido por `security/runner.py` y `quality/runner.py` -- la única
diferencia entre ambos es qué escáneres corren; la lógica de "reemplazar los
hallazgos viejos de este archivo por los nuevos, dejando el resto del
ScanResult intacto, y calcular qué se resolvió/persiste/apareció" es idéntica.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import Finding, ScanResult


def merge_file_findings(
    previous: ScanResult | None,
    root: Path,
    file_rel: str,
    new_file_findings: list[Finding],
    tools_run: list[str],
    tools_skipped: dict[str, str],
) -> tuple[ScanResult, list[Finding], list[Finding], list[Finding]]:
    """Devuelve (ScanResult actualizado, resueltos, persistentes, nuevos).

    "Resueltos" = tenían un id en el escaneo anterior para este archivo y ya
    no aparecen -- no se infiere que el fix puntual los causó, solo que ya no
    están (mismo criterio que pidió el usuario: diff de ids, no causalidad).
    `scanned_at` SÍ se actualiza a "ahora" aunque sea un rescan parcial -- es
    el timestamp de "última vez que se tocó este cache", útil para que la UI
    detecte que hay novedades sin necesitar un campo aparte."""
    old_file_findings = [f for f in (previous.findings if previous else []) if f.file == file_rel]
    old_by_id = {f.id: f for f in old_file_findings}
    new_by_id = {f.id: f for f in new_file_findings}

    resolved = [f for fid, f in old_by_id.items() if fid not in new_by_id]
    persisting = [f for fid, f in old_by_id.items() if fid in new_by_id]
    brand_new = [f for fid, f in new_by_id.items() if fid not in old_by_id]

    other_findings = [f for f in (previous.findings if previous else []) if f.file != file_rel]
    merged_findings = other_findings + new_file_findings

    result = ScanResult(
        root=str(root),
        scanned_at=datetime.now(timezone.utc).isoformat(),
        tools_run=sorted(set((previous.tools_run if previous else [])) | set(tools_run)),
        tools_skipped={**(previous.tools_skipped if previous else {}), **tools_skipped},
        findings=merged_findings,
    )
    return result, resolved, persisting, brand_new
