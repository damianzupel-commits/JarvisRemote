"""Paso de 'testear real' del pipeline de auditoría (crear -> auditar ->
corregir -> TESTEAR -> re-auditar, ver la sesión de meta-observación
2026-08-10) -- detecta y corre la suite de tests real de un proyecto después
de un fix, para que 'compiló' deje de poder confundirse con 'funciona'.

Mismo criterio de separación que `app/security/` y `app/quality/`: acá vive la
lógica real (detección + ejecución + cache del último resultado), y
`app/tools/test_run.py` es el wrapper fino que la expone al LLM."""
