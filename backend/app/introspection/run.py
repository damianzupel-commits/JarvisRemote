"""CLI para correr el análisis de meta-observación sobre `audit.log` ya
generado por sesiones pasadas del agente (ver `analyzer.py` para el diseño).

No corre en tiempo real -- se ejecuta después de una sesión, o on-demand,
como pidió Damian explícitamente para esta primera versión (Opción B).

Uso:
    python -m app.introspection.run                  # analiza TODAS las conversaciones
    python -m app.introspection.run <conversation_id> # analiza una sola
"""

from __future__ import annotations

import sys

from . import analyzer


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    conversation_id = argv[0] if argv else None

    findings = (
        analyzer.analyze_conversation(conversation_id) if conversation_id else analyzer.analyze_all()
    )

    if not findings:
        scope = f"conversación '{conversation_id}'" if conversation_id else "todas las conversaciones"
        print(f"No se detectaron patrones de falla conocidos en {scope}.")
        return 0

    for finding in findings:
        note = analyzer.write_finding_note(finding)
        print(
            f"[{finding.pattern}] conv={finding.conversation_id} path={finding.path} "
            f"-> nota guardada: {note.id}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
