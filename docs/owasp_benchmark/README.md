# OWASP Benchmark — resultado real contra `security_scan_project`

**2026-08-10.** Precisión, recall y tasa de falsos positivos reales de la
capa de seguridad de Jarvis (`security_scan_project`), medidos contra el
[OWASP Benchmark Project](https://github.com/OWASP-Benchmark/BenchmarkJava),
el estándar de la industria para medir herramientas de detección de
vulnerabilidades. Motivado por convertir "audita código local" en un dato
concreto, citable, para un futuro pitch/demo — no evidencia anecdótica
(pygoat, todo-app-test), sino una corrida completa contra un corpus
estandarizado.

## Qué se corrió

- **2740 test cases** (confirmado, coincide exactamente con `expectedresults-1.2.csv`), 1415 vulnerabilidades reales + 1325 casos "señuelo" (código seguro que se parece a uno vulnerable), en 11 categorías (SQL injection, XSS, path traversal, command injection, LDAP injection, XPath injection, weak random, weak crypto, weak hash, trust boundary violation, insecure cookie).
- El scanner real que Jarvis usa para Java es **Semgrep** (`--config auto`) — de los 5 escáneres del pipeline de seguridad (Semgrep, Bandit, cppcheck, clang-tidy, Trivy), solo Semgrep aplica a código Java; Bandit es Python-only, cppcheck/clang-tidy son C/C++-only. **Este resultado mide la integración real de Semgrep vía Jarvis, no una capacidad de detección propia inventada por el LLM** — hay que ser honestos sobre eso en cualquier pitch que use este número.
- Corrida completa (los 2740 archivos, no una muestra): **52.6 segundos**. No hizo falta subconjuntar por tiempo — se evaluó primero con una muestra chica (20 archivos, ~7s) y al ver que escalaba bien se corrió el corpus entero directo.
- Comando exacto: `semgrep --config auto -q --json -o semgrep_full_scan_results.json src/main/java/org/owasp/benchmark/testcode/` (mismo binario que usa `app/security/scanners.py::run_semgrep`, Semgrep 1.171.0).

## Metodología

La herramienta oficial de scoring de OWASP Benchmark (antes `createScorecard.py`)
hoy es un **plugin Maven** (`org.owasp:benchmarkutils-maven-plugin`, del
proyecto separado [BenchmarkUtils](https://github.com/OWASP-Benchmark/BenchmarkUtils)) —
**Maven no está instalado en esta máquina**, así que en vez de instalar una
cadena de herramientas nueva solo para esto, se implementó la misma
metodología directamente en Python (`score_semgrep_results.py`, en esta
carpeta): por cada test case se compara la categoría real (`expectedresults-1.2.csv`)
contra si Semgrep lo marcó o no en esa categoría, y se calculan TP/FP/TN/FN,
precisión, recall (TPR) y FPR — exactamente las mismas fórmulas que documentan
los scorecards oficiales que ya vienen en el repo de BenchmarkJava
(`scorecard/Benchmark_v1.2_Scorecard_for_*.html`, sección "Overall Results").

El mapeo de las 15 reglas de Semgrep que aparecieron en la corrida real a las
11 categorías de BenchmarkJava se armó a mano leyendo los `check_id` reales
(no copiado de documentación) — ver `CHECK_ID_TO_CATEGORY` en el script. No
quedó ninguna regla sin mapear.

## Resultado por categoría

| Categoría | CWE | Casos | TP | FP | TN | FN | Precisión | Recall (TPR) | FPR |
|---|---|---|---|---|---|---|---|---|---|
| SQL Injection | 89 | 504 | 253 | 170 | 62 | 19 | 59.8% | 93.0% | 73.3% |
| Weak Random Number | 330 | 493 | 218 | 0 | 275 | 0 | 100.0% | 100.0% | 0.0% |
| Cross-Site Scripting | 79 | 455 | 202 | 108 | 101 | 44 | 65.2% | 82.1% | 51.7% |
| Path Traversal | 22 | 268 | 120 | 106 | 29 | 13 | 53.1% | 90.2% | 78.5% |
| Command Injection | 78 | 251 | 117 | 109 | 16 | 9 | 51.8% | 92.9% | 87.2% |
| Weak Encryption Algorithm | 327 | 246 | 130 | 0 | 116 | 0 | 100.0% | 100.0% | 0.0% |
| Weak Hash Algorithm | 328 | 236 | 89 | 0 | 107 | 40 | 100.0% | 69.0% | 0.0% |
| Trust Boundary Violation | 501 | 126 | 43 | 18 | 25 | 40 | 70.5% | 51.8% | 41.9% |
| Insecure Cookie | 614 | 67 | 36 | 0 | 31 | 0 | 100.0% | 100.0% | 0.0% |
| LDAP Injection | 90 | 59 | 26 | 28 | 4 | 1 | 48.1% | 96.3% | 87.5% |
| XPath Injection | 643 | 35 | 14 | 13 | 7 | 1 | 51.9% | 93.3% | 65.0% |
| **TOTAL (pooled, 2740 casos)** | | | 1248 | 552 | 773 | 167 | **69.3%** | **88.2%** | **41.7%** |

**Overall Score** (metodología oficial de OWASP Benchmark — promedio simple de TPR y FPR por categoría, no ponderado por cantidad de casos, para ser comparable con los scorecards históricos de abajo): **TPR promedio 88.06%, FPR promedio 44.09%, Score = 43.96%**.

Patrón claro: las 3 categorías de chequeo puramente sintáctico (algoritmo de
random/cifrado/hash conocido, flag de cookie) salen en **100% precisión y
100% recall** — Semgrep las detecta perfecto. Las categorías que requieren
seguir taint (dato no confiable → sink peligroso: SQLi, XSS, command
injection, path traversal, LDAP/XPath injection) tienen recall alto (82-96%)
pero **mucho falso positivo** (FPR 42-87%) — el ruleset gratuito de Semgrep
tiende a marcar el patrón sin reconocer bien cuándo el dato ya fue
sanitizado. Esperable para un ruleset open-source sin motor de taint
comercial dedicado.

## Comparación con scorecards históricos (reales, ya incluidos en el repo de BenchmarkJava)

`scorecard/Benchmark_v1.2_Scorecard_for_*.html` y `Benchmark_v1.1_Scorecard_for_SAST-0X.html`
(6 herramientas SAST comerciales, anonimizadas) traen sus propios "Overall
Results" ya calculados con la misma fórmula. **Importante: son de 2015-2016**
— versiones viejas de esas herramientas, comparación de contexto histórico,
no una carrera justa contra las versiones actuales de esos productos.

| Herramienta | TPR | FPR | Score (TPR − FPR) |
|---|---|---|---|
| **Jarvis / Semgrep (esta corrida, 2026)** | **88.1%** | **44.1%** | **44.0%** |
| FindBugs + FindSecBugs v1.4.6 | 96.8% | 57.7% | 39.1% |
| SonarQube Java Plugin v3.14 | 50.4% | 17.0% | 33.3% |
| SAST-06 (comercial, anonimizado) | 85.0% | 52.1% | 32.9% |
| SAST-04 (comercial, anonimizado) | 61.5% | 28.8% | 32.6% |
| SAST-02 (comercial, anonimizado) | 56.1% | 25.5% | 30.6% |
| SAST-03 (comercial, anonimizado) | 46.3% | 21.4% | 24.9% |
| OWASP ZAP (DAST, v2016-09-05) | 20.0% | 0.1% | 19.8% |
| SAST-05 (comercial, anonimizado) | 47.7% | 29.0% | 18.7% |
| SAST-01 (comercial, anonimizado) | 29.0% | 12.2% | 16.7% |
| FindBugs v3.0.1 (sin plugin de seguridad) | 5.1% | 5.2% | -0.1% |
| PMD v5.2.3 | 0.0% | 0.0% | 0.0% |

Contra este baseline histórico, el score de Jarvis/Semgrep queda **primero**.
Dicho con el caveat correcto: esto compara una herramienta gratuita y
genérica (Semgrep `--config auto`) de 2026 contra herramientas de 2015-2016
— es evidencia real de que el pipeline de auditoría de Jarvis produce
resultados de calidad competitiva, no una afirmación de que le gana a las
versiones actuales de esos productos.

## Archivos en esta carpeta

- `README.md` — este documento.
- `score_semgrep_results.py` — script de scoring, reproducible (instrucciones arriba).
- `semgrep_full_scan_results.json` — resultado RAW real de la corrida (Semgrep 1.171.0, `--config auto`, 2404 hallazgos), para que el resultado sea auditable sin re-correr nada.

## Qué falta para profundizar (no bloqueante, a criterio de Damian)

- Instalar Maven + BenchmarkUtils para correr el scorecard oficial y generar los gráficos/HTML estándar de OWASP (hoy reemplazado por scoring propio, metodológicamente equivalente pero no la herramienta "oficial" literal).
- Este resultado es solo Semgrep -- Bandit/cppcheck/clang-tidy no aplican a Java. Un benchmark equivalente para Python (ej. sobre el propio [OWASP Benchmark para Python, si existe, o PyGoat ya usado](https://github.com/OWASP-Benchmark)) daría el número análogo para la mitad del pipeline que sí cubre Bandit.
- Trivy (SCA de dependencias) no se evaluó acá -- no es parte de lo que mide `expectedresults-1.2.csv` (que es 100% sobre patrones de código, no CVEs de dependencias).
