"""Compila un reporte legible (Markdown) de auditoría de código para un
proyecto: hallazgos abiertos (seguridad + calidad), qué fixes/ediciones ya se
aplicaron (con su commit de git, todos revertibles) y un resumen ejecutivo.
Se guarda como nota en el vault de Obsidian (autor "jarvis", ver
`app/obsidian/vault.py`) para que quede versionado y visible en la pestaña
Obsidian de la UI -- no solo como texto de chat que se pierde apenas se cierra
la conversación.

Lee del cache de escaneos (`security/store.py`, `quality/store.py`) y del log
de auditoría (`audit_log.read_entries`) -- no vuelve a correr ningún escáner
ni inventa qué se aplicó, solo compila lo que ya quedó registrado.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from . import audit_log
from .findings.models import Finding
from .findings.noise import KNOWN_NOISE_RULES as _KNOWN_NOISE_RULES
from .findings.noise import SEVERITY_ORDER as _SEVERITY_ORDER
from .findings.noise import split_noise as _split_noise
from .obsidian import vault
from .quality import store as quality_store
from .security import store as security_store

_MAX_FINDINGS_PER_SECTION = 200


def _severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _entry_matches_root(entry: dict, root: Path) -> bool:
    args = entry.get("arguments") or {}
    raw = args.get("path")
    if not raw:
        return False
    try:
        return Path(raw).resolve() == root
    except OSError:
        return False


def _findings_table(title: str, findings: list[Finding]) -> list[str]:
    lines = [f"## {title} ({len(findings)})", ""]
    if not findings:
        lines.append("Ninguno.")
        lines.append("")
        return lines

    lines.append("| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |")
    lines.append("|---|---|---|---|---|")
    # El ruido conocido (ver _KNOWN_NOISE_RULES) se ordena al final de la tabla,
    # después de todo lo demás por severidad -- sigue visible, pero no compite
    # por atención con los hallazgos reales.
    ordered = sorted(
        findings,
        key=lambda f: (f.rule_id in _KNOWN_NOISE_RULES, _SEVERITY_ORDER.get(f.severity, 9), f.file, f.line),
    )
    for f in ordered[:_MAX_FINDINGS_PER_SECTION]:
        msg = f.message.replace("|", "\\|").replace("\n", " ").strip()[:160]
        rule_label = f"`{f.rule_id}` ({f.tool})"
        if f.rule_id in _KNOWN_NOISE_RULES:
            rule_label += " -- ruido conocido"
        lines.append(f"| {f.severity} | `{f.file}` | {f.line} | {rule_label} | {msg} |")
    if len(findings) > _MAX_FINDINGS_PER_SECTION:
        lines.append("")
        lines.append(f"_(+{len(findings) - _MAX_FINDINGS_PER_SECTION} más, omitidos por espacio)_")
    lines.append("")
    return lines


def generate_report(path: str) -> dict:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    sec_scan = security_store.load_scan(root)
    qual_scan = quality_store.load_scan(root)
    if sec_scan is None and qual_scan is None:
        raise ValueError(
            "No hay escaneos guardados para este proyecto -- corré security_scan_project y/o "
            "quality_scan_project antes de generar el reporte."
        )

    sec_findings = sec_scan.findings if sec_scan else []
    qual_findings = qual_scan.findings if qual_scan else []
    sec_real, sec_noise = _split_noise(sec_findings)
    qual_real, qual_noise = _split_noise(qual_findings)
    sec_counts = _severity_counts(sec_real)
    qual_counts = _severity_counts(qual_real)

    fix_entries = [
        e
        for e in audit_log.read_entries(tool="code_apply_fix")
        if e.get("ok") and (e.get("result") or {}).get("committed") and _entry_matches_root(e, root)
    ]
    edit_entries = [
        e
        for e in audit_log.read_entries(tool="fs_write_file")
        if e.get("ok") and (e.get("result") or {}).get("committed") and _entry_matches_root(e, root)
    ]

    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [f"# Reporte de auditoría de código -- {root.name}", ""]
    lines.append(f"- Proyecto: `{root}`")
    lines.append(f"- Generado: {generated_at}")
    if sec_scan:
        lines.append(
            f"- Último escaneo de seguridad: {sec_scan.scanned_at} "
            f"(corrieron: {', '.join(sec_scan.tools_run) or 'ninguno'})"
        )
    if qual_scan:
        lines.append(
            f"- Último escaneo de calidad: {qual_scan.scanned_at} "
            f"(corrieron: {', '.join(qual_scan.tools_run) or 'ninguno'})"
        )
    lines.append("")

    lines.append("## Resumen ejecutivo")
    lines.append("")
    total_open = len(sec_real) + len(qual_real)
    total_noise = len(sec_noise) + len(qual_noise)
    summary_bits = []
    if sec_real:
        summary_bits.append(
            f"{len(sec_real)} hallazgo(s) de seguridad real(es) "
            f"({sec_counts.get('critical', 0)} crítico(s), {sec_counts.get('high', 0)} alto(s))"
        )
    if qual_real:
        summary_bits.append(
            f"{len(qual_real)} hallazgo(s) de calidad ({qual_counts.get('high', 0)} de severidad 'alta' "
            "según el propio analizador (Ruff/mypy/ESLint/tsc, el que haya corrido) -- no es un nivel de riesgo "
            "de seguridad)"
        )
    if fix_entries or edit_entries:
        summary_bits.append(
            f"{len(fix_entries)} fix(es) y {len(edit_entries)} edición(es) general(es) ya aplicados, "
            "todos revertibles con git revert"
        )
    if total_open == 0 and not summary_bits:
        lines.append("Sin hallazgos abiertos y sin actividad registrada todavía.")
    elif total_open == 0:
        lines.append("Sin hallazgos reales abiertos. " + ". ".join(summary_bits) + ".")
    else:
        lines.append(". ".join(summary_bits) + ".")
    if total_noise:
        noise_rule_ids = sorted({f.rule_id for f in sec_noise + qual_noise})
        noise_desc = "; ".join(f"{rid} ({_KNOWN_NOISE_RULES[rid]})" for rid in noise_rule_ids)
        lines.append("")
        lines.append(
            f"_Se excluyeron {total_noise} hallazgo(s) del conteo de arriba por ser ruido conocido: {noise_desc}. "
            "No se descartaron del escaneo -- siguen en las tablas de detalle más abajo, marcados como tal._"
        )
    lines.append("")

    lines += _findings_table("Hallazgos de seguridad", sec_findings)
    lines += _findings_table("Hallazgos de calidad", qual_findings)

    lines.append(f"## Fixes aplicados ({len(fix_entries)})")
    lines.append("")
    if not fix_entries:
        lines.append("Ninguno todavía.")
    else:
        lines.append("| Commit | Archivo | Mensaje |")
        lines.append("|---|---|---|")
        for e in fix_entries:
            result = e.get("result") or {}
            args = e.get("arguments") or {}
            commit_hash = result.get("commit_hash") or "?"
            file_ = result.get("file") or args.get("file") or "?"
            message = (args.get("commit_message") or "").replace("|", "\\|")
            lines.append(f"| `{commit_hash}` | `{file_}` | {message} |")
    lines.append("")

    lines.append(f"## Ediciones generales auditadas ({len(edit_entries)})")
    lines.append("")
    lines.append(
        "Escrituras vía fs_write_file dentro de este proyecto (ya indexado por Codebase y con git) -- "
        "no vienen de un hallazgo puntual, pero pasan por el mismo circuito auditado y reversible."
    )
    lines.append("")
    if not edit_entries:
        lines.append("Ninguna todavía.")
    else:
        lines.append("| Commit | Archivo |")
        lines.append("|---|---|")
        for e in edit_entries:
            result = e.get("result") or {}
            args = e.get("arguments") or {}
            commit_hash = result.get("commit_hash") or "?"
            file_ = args.get("file") or "?"
            lines.append(f"| `{commit_hash}` | `{file_}` |")
    lines.append("")

    content = "\n".join(lines)
    note = vault.save_note(
        title=f"Reporte de auditoría -- {root.name} -- {generated_at[:10]}",
        content=content,
        author="jarvis",
        tags=["reportes", "auditoria", "seguridad", "calidad"],
    )

    return {
        "note_id": note.id,
        "note_title": note.title,
        "project": str(root),
        "security_findings": len(sec_findings),
        "quality_findings": len(qual_findings),
        "fixes_applied": len(fix_entries),
        "general_edits_applied": len(edit_entries),
        "content_preview": content[:2000],
    }
