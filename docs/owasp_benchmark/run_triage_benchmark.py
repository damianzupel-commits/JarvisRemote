"""Corre el triage con LLM (app.security.triage) sobre TODOS los hallazgos
crudos de la corrida de Semgrep contra OWASP Benchmark (2404 hallazgos,
docs/owasp_benchmark/semgrep_full_scan_results.json), para validar
empiricamente si baja el falso positivo medido el 2026-08-10 (TPR 88.1%,
FPR 44.1%, Score 44.0%) sin destruir el recall.

Diseñado para una corrida larga (horas) sin supervision constante:
- Resumible: cada veredicto se escribe (append, flush inmediato) a
  triage_raw_results.jsonl apenas se obtiene -- si el proceso se corta a
  mitad de camino, la proxima corrida retoma donde quedo, no repite nada.
- Se puede invocar con --limit N para procesar como mucho N hallazgos
  pendientes en esta invocacion (por chequeos de progreso periodicos), o sin
  --limit para procesar todos los que falten.
- Imprime, cada 20 hallazgos, el ritmo real de la ULTIMA ventana (no el
  promedio de toda la corrida, que diluiria un cambio de ritmo reciente) y
  el tiempo total proyectado restante con ese ritmo.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\dam\Documents\JarvisRemote\backend")

from app.findings.models import Finding, make_finding_id  # noqa: E402
from app.security import triage  # noqa: E402

BENCHMARK_ROOT = Path(r"C:\Users\dam\Documents\test-scans\OWASP-BenchmarkJava")
RAW_SEMGREP_JSON = Path(r"C:\Users\dam\Documents\JarvisRemote\docs\owasp_benchmark\semgrep_full_scan_results.json")
OUTPUT_JSONL = Path(r"C:\Users\dam\Documents\JarvisRemote\docs\owasp_benchmark\triage_raw_results.jsonl")

_SEMGREP_SEVERITY = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}

# mismo mapeo que score_owasp_benchmark.py -- se repite acá para que este
# script no dependa de rutas de import cruzadas del scorer.
CHECK_ID_TO_CATEGORY = {
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


def load_all_findings() -> list[Finding]:
    data = json.loads(RAW_SEMGREP_JSON.read_text(encoding="utf-8"))
    findings = []
    for r in data["results"]:
        extra = r.get("extra", {})
        file_rel = r["path"].replace("\\", "/")
        line = r["start"]["line"]
        rule_id = r["check_id"]
        findings.append(
            Finding(
                id=make_finding_id("semgrep", file_rel, line, rule_id),
                tool="semgrep", file=file_rel, line=line,
                end_line=r.get("end", {}).get("line"),
                severity=_SEMGREP_SEVERITY.get(extra.get("severity", ""), "medium"),
                rule_id=rule_id, message=extra.get("message", "").strip(),
            )
        )
    return findings


def load_done_ids() -> set[str]:
    if not OUTPUT_JSONL.is_file():
        return set()
    done = set()
    for line in OUTPUT_JSONL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            done.add(json.loads(line)["id"])
        except (json.JSONDecodeError, KeyError):
            continue
    return done


async def main(limit: int | None) -> None:
    all_findings = load_all_findings()
    done_ids = load_done_ids()
    pending = [f for f in all_findings if f.id not in done_ids]
    print(f"Total: {len(all_findings)}  Ya hechos: {len(done_ids)}  Pendientes: {len(pending)}", flush=True)

    if limit is not None:
        pending = pending[:limit]
        print(f"Esta invocacion procesa hasta {limit}: {len(pending)} en esta corrida.", flush=True)

    if not pending:
        print("Nada pendiente -- ya está todo triageado.", flush=True)
        return

    window_times: list[float] = []
    start_all = time.time()
    with OUTPUT_JSONL.open("a", encoding="utf-8") as out:
        for i, f in enumerate(pending, 1):
            t0 = time.time()
            try:
                verdict = await triage.triage_finding(BENCHMARK_ROOT, f)
            except Exception as exc:
                verdict = triage.TriageVerdict(verdict="real", reasoning=f"error en triage: {exc}")
            dt = time.time() - t0
            window_times.append(dt)

            record = {
                "id": f.id, "file": f.file, "line": f.line, "rule_id": f.rule_id,
                "category": CHECK_ID_TO_CATEGORY.get(f.rule_id),
                "verdict": verdict.verdict, "reasoning": verdict.reasoning,
                "elapsed_seconds": round(dt, 2),
            }
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            out.flush()

            if i % 20 == 0 or i == len(pending):
                recent = window_times[-20:]
                mean_recent = sum(recent) / len(recent)
                remaining_total = len(all_findings) - (len(done_ids) + i)
                eta_min = remaining_total * mean_recent / 60
                elapsed_min = (time.time() - start_all) / 60
                print(
                    f"[{i}/{len(pending)}] hecho={len(done_ids)+i}/{len(all_findings)}  "
                    f"ritmo_reciente={mean_recent:.1f}s/call  transcurrido={elapsed_min:.1f}min  "
                    f"ETA_restante={eta_min:.1f}min (~{eta_min/60:.2f}h)",
                    flush=True,
                )

    print("Listo esta invocacion.", flush=True)


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(main(limit_arg))
