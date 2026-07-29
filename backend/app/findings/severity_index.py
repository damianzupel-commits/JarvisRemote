"""Agrega los hallazgos ya cacheados de seguridad y calidad (`security/store.py`,
`quality/store.py`) por archivo, quedándose con la severidad máxima de cada uno.

Lo consume `GET /api/codebase/graph` para pintar el halo de riesgo del grafo 3D
(ver `ui/graph_view.py` + `ui/web_assets/graph3d.html` del lado de tray-app) sin
volver a correr los escáneres -- ambos stores ya persisten su último resultado en
disco (`security_scan_dir`/`quality_scan_dir`), acá solo se agrupan por path. No
hace falta un tercer archivo de cache: recalcular esto es sumar unos cientos de
findings en memoria, mucho más barato que el propio `load_scan` (leer y parsear
el JSON) que ya se paga en cada llamada.
"""

from __future__ import annotations

from pathlib import Path

from ..quality import store as quality_store
from ..security import store as security_store
from .models import ScanResult
from .noise import SEVERITY_ORDER, split_noise

SEVERITY_RANK: dict[str, int] = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _higher_severity(current: str | None, candidate: str) -> str:
    if current is None:
        return candidate
    return candidate if SEVERITY_RANK.get(candidate, 0) > SEVERITY_RANK.get(current, 0) else current


def build_file_risk_index(root: str | Path) -> dict:
    """Devuelve:
    {
      "files": {"<path relativo>": {"severity": "critical", "finding_count": 3}, ...},
      "security_scanned": bool, "security_scanned_at": str | None,
      "quality_scanned": bool, "quality_scanned_at": str | None,
    }

    Un path que no aparece en "files" no tuvo hallazgos -- pero eso puede
    significar "se escaneó y salió limpio" o "todavía no se escaneó"; quien
    llama debe mirar `security_scanned`/`quality_scanned` para no confundir
    ambos casos (ver requisito de no pintar un halo falso de "sin hallazgos"
    en un proyecto que nunca se escaneó)."""
    root_path = Path(root).resolve()
    security_scan = security_store.load_scan(root_path)
    quality_scan = quality_store.load_scan(root_path)

    files: dict[str, dict] = {}

    def _absorb(scan: ScanResult | None) -> None:
        if scan is None:
            return
        for finding in scan.findings:
            entry = files.setdefault(finding.file, {"severity": None, "finding_count": 0})
            entry["finding_count"] += 1
            entry["severity"] = _higher_severity(entry["severity"], finding.severity)

    _absorb(security_scan)
    _absorb(quality_scan)

    return {
        "files": files,
        "security_scanned": security_scan is not None,
        "security_scanned_at": security_scan.scanned_at if security_scan else None,
        "quality_scanned": quality_scan is not None,
        "quality_scanned_at": quality_scan.scanned_at if quality_scan else None,
    }


def list_file_findings(root: str | Path, file_rel: str) -> dict:
    """Hallazgos de seguridad+calidad de UN archivo puntual, ordenados por
    severidad descendente (crítico primero), para el panel de lectura de
    código de la pestaña Codebase (`GET /api/codebase/file`) -- "de un
    vistazo" quiere decir que el ruido conocido (`findings/noise.py`) se
    excluye del todo acá, no solo se lo manda al final como en el reporte
    ejecutivo completo (ese panel tiene mucho menos espacio en pantalla)."""
    root_path = Path(root).resolve()
    security_scan = security_store.load_scan(root_path)
    quality_scan = quality_store.load_scan(root_path)

    all_findings = []
    if security_scan:
        all_findings += [f for f in security_scan.findings if f.file == file_rel]
    if quality_scan:
        all_findings += [f for f in quality_scan.findings if f.file == file_rel]

    real, noise = split_noise(all_findings)
    real_sorted = sorted(real, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.line))

    return {
        "findings": [f.to_dict() for f in real_sorted],
        "noise_omitted": len(noise),
        "security_scanned": security_scan is not None,
        "quality_scanned": quality_scan is not None,
    }
