"""Re-exporta el modelo de hallazgos compartido -- ver `app/findings/models.py`.
`security/` (vulnerabilidades) y `quality/` (bugs generales) usan el mismo
esquema de `Finding`/`ScanResult`, así que vive en un solo lugar; este módulo
se mantiene para no romper el import existente `from app.security.models
import Finding` usado en tests y en el resto de `security/`."""

from __future__ import annotations

from ..findings.models import Finding, ScanResult, make_finding_id

__all__ = ["Finding", "ScanResult", "make_finding_id"]
