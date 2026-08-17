"""Validación en subconjunto: re-triagea SOLO los hallazgos de las 3
categorías que peor salieron (trustbound, ldapi, pathtraver) con la
referencia curada ya wireada, para confirmar que mejora antes de comprometer
tiempo a la corrida completa de 2404 de nuevo. Mismo patrón resumible que
run_triage_benchmark.py."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\dam\Documents\JarvisRemote\backend")

from app.findings.models import Finding, make_finding_id  # noqa: E402
from app.security import triage  # noqa: E402
from app.security.rule_categories import CHECK_ID_TO_CATEGORY  # noqa: E402

BENCHMARK_ROOT = Path(r"C:\Users\dam\Documents\test-scans\OWASP-BenchmarkJava")
RAW_SEMGREP_JSON = Path(r"C:\Users\dam\Documents\JarvisRemote\docs\owasp_benchmark\semgrep_full_scan_results.json")
OUTPUT_JSONL = Path(r"C:\Users\dam\Documents\JarvisRemote\docs\owasp_benchmark\triage_subset_validation.jsonl")

TARGET_CATEGORIES = {"trustbound", "ldapi", "pathtraver"}
_SEMGREP_SEVERITY = {"ERROR": "high", "WARNING": "medium", "INFO": "low"}


def load_target_findings() -> list[Finding]:
    data = json.loads(RAW_SEMGREP_JSON.read_text(encoding="utf-8"))
    findings = []
    for r in data["results"]:
        rule_id = r["check_id"]
        if CHECK_ID_TO_CATEGORY.get(rule_id) not in TARGET_CATEGORIES:
            continue
        extra = r.get("extra", {})
        file_rel = r["path"].replace("\\", "/")
        line = r["start"]["line"]
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


async def main() -> None:
    all_findings = load_target_findings()
    done_ids = load_done_ids()
    pending = [f for f in all_findings if f.id not in done_ids]
    print(f"Total subconjunto: {len(all_findings)}  Ya hechos: {len(done_ids)}  Pendientes: {len(pending)}", flush=True)

    if not pending:
        print("Nada pendiente.", flush=True)
        return

    window_times: list[float] = []
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
                remaining = len(pending) - i
                eta_min = remaining * mean_recent / 60
                print(f"[{i}/{len(pending)}]  ritmo_reciente={mean_recent:.1f}s/call  ETA={eta_min:.1f}min", flush=True)

    print("Listo.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
