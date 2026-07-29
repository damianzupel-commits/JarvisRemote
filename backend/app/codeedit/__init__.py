"""Circuito auditado y reversible para escrituras de código: dry-run + diff
por default, y recién escribe + commitea (commit propio, revertible con `git
revert`) si se confirma. Ver `fixer.py`.

Usado por `code_apply_fix` (fixes de seguridad/calidad, ver
`app/tools/code_edit.py`) y por `fs_write_file` (`app/tools/filesystem.py`)
cuando el archivo cae dentro de un proyecto ya indexado por Codebase -- mismo
circuito para cualquier escritura de código, no solo fixes puntuales de un
hallazgo.
"""
