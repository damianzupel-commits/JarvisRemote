"""Scoring standalone contra OWASP Benchmark (BenchmarkJava) para los
resultados reales de Semgrep (--config auto), tal como lo corre
`app/security/scanners.py::run_semgrep` dentro de `security_scan_project`.

Metodologia = la misma que usa la herramienta oficial de scoring de OWASP
Benchmark (BenchmarkUtils, hoy un plugin Maven -- no instalado en esta
maquina, ver justificacion en el informe): por cada test case (un archivo
Java, con una categoria/CWE y un ground truth real-vulnerabilidad true/false
en expectedresults-1.2.csv), se compara contra si Jarvis lo marco o no en esa
categoria, y se calcula TP/FP/TN/FN, precision, recall (TPR) y FPR por
categoria y total.

Mapeo check_id de Semgrep -> categoria de BenchmarkJava: construido a mano
leyendo los 15 check_id reales que aparecieron en la corrida completa (no
inventado ni copiado de documentacion de Semgrep) -- ver la lista abajo.

Para reproducir desde cero (el repo de BenchmarkJava, ~243MB/2740 archivos
Java, no se vendorea dentro de JarvisRemote):
    git clone --depth 1 https://github.com/OWASP-Benchmark/BenchmarkJava.git
    cd BenchmarkJava
    <ruta-a-jarvis>/backend/.venv/Scripts/semgrep.exe --config auto -q --json \
        -o semgrep_full_scan_results.json src/main/java/org/owasp/benchmark/testcode/
    python score_semgrep_results.py

`semgrep_full_scan_results.json` (al lado de este script) es el resultado RAW
real de esa corrida (2026-08-10, Semgrep 1.171.0, --config auto) -- se guarda
en el repo para que el resultado sea auditable sin tener que re-clonar/re-correr
nada.
"""
import csv
import json
import os
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
EXPECTED_CSV = r"C:\Users\dam\Documents\test-scans\OWASP-BenchmarkJava\expectedresults-1.2.csv"
SEMGREP_JSON = os.path.join(_HERE, "semgrep_full_scan_results.json")

# check_id real -> categoria de BenchmarkJava (11 categorias, 1 CWE c/u)
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

CATEGORY_LABEL = {
    "sqli": "SQL Injection", "weakrand": "Weak Random Number", "xss": "Cross-Site Scripting",
    "pathtraver": "Path Traversal", "cmdi": "Command Injection", "crypto": "Weak Encryption Algorithm",
    "hash": "Weak Hash Algorithm", "trustbound": "Trust Boundary Violation",
    "securecookie": "Insecure Cookie", "ldapi": "LDAP Injection", "xpathi": "XPath Injection",
}


def load_expected():
    expected = {}
    with open(EXPECTED_CSV, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            name, category, real_vuln, cwe = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip()
            expected[name] = {"category": category, "real": real_vuln == "true", "cwe": cwe}
    return expected


def load_flagged():
    """set of (test_name, category) que Semgrep marco de verdad."""
    with open(SEMGREP_JSON, encoding="utf-8") as f:
        data = json.load(f)
    flagged = set()
    unmapped = defaultdict(int)
    for r in data["results"]:
        check_id = r["check_id"]
        path = r["path"].replace("\\", "/")
        test_name = path.rsplit("/", 1)[-1].replace(".java", "")
        category = CHECK_ID_TO_CATEGORY.get(check_id)
        if category is None:
            unmapped[check_id] += 1
            continue
        flagged.add((test_name, category))
    return flagged, unmapped


def score():
    expected = load_expected()
    flagged, unmapped = load_flagged()

    per_category = defaultdict(lambda: {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
    overall = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}

    for name, info in expected.items():
        category = info["category"]
        is_real = info["real"]
        was_flagged = (name, category) in flagged

        if is_real and was_flagged:
            key = "tp"
        elif is_real and not was_flagged:
            key = "fn"
        elif not is_real and was_flagged:
            key = "fp"
        else:
            key = "tn"

        per_category[category][key] += 1
        overall[key] += 1

    def metrics(c):
        tp, fp, tn, fn = c["tp"], c["fp"], c["tn"], c["fn"]
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        fpr = fp / (fp + tn) if (fp + tn) else None
        return precision, recall, fpr, tp, fp, tn, fn

    print(f"{'Categoria':<14} {'CWE':<5} {'N':<6} {'TP':<5} {'FP':<5} {'TN':<5} {'FN':<5} {'Precision':<10} {'Recall':<8} {'FPR':<8}")
    rows_for_md = []
    for category in sorted(per_category, key=lambda c: -sum(per_category[c].values())):
        c = per_category[category]
        n = sum(c.values())
        precision, recall, fpr, tp, fp, tn, fn = metrics(c)
        cwe = next(v["cwe"] for v in expected.values() if v["category"] == category)
        p_s = f"{precision:.1%}" if precision is not None else "n/a"
        r_s = f"{recall:.1%}" if recall is not None else "n/a"
        f_s = f"{fpr:.1%}" if fpr is not None else "n/a"
        print(f"{category:<14} {cwe:<5} {n:<6} {tp:<5} {fp:<5} {tn:<5} {fn:<5} {p_s:<10} {r_s:<8} {f_s:<8}")
        rows_for_md.append((CATEGORY_LABEL[category], cwe, n, tp, fp, tn, fn, p_s, r_s, f_s))

    print()
    precision, recall, fpr, tp, fp, tn, fn = metrics(overall)
    print(f"{'TOTAL (pooled)':<14} {'':<5} {sum(overall.values()):<6} {tp:<5} {fp:<5} {tn:<5} {fn:<5} {precision:.1%}      {recall:.1%}    {fpr:.1%}")

    # "Overall Score" con la MISMA metodologia que usan los scorecards
    # oficiales de OWASP Benchmark (ver Benchmark_v1.2_Scorecard_for_*.html en
    # este repo, seccion "Overall Results*"): promedio simple de TPR y de FPR
    # por categoria (NO ponderado por cantidad de test cases de cada
    # categoria), y Score = promedio(TPR) - promedio(FPR). Reportado aparte del
    # TOTAL pooled de arriba porque son dos estadisticos distintos y no
    # intercambiables -- el oficial es el que hace comparable este resultado
    # contra los scorecards historicos ya guardados en este mismo repo.
    tprs, fprs = [], []
    for category in per_category:
        _, recall_c, fpr_c, *_ = metrics(per_category[category])
        tprs.append(recall_c or 0.0)
        fprs.append(fpr_c or 0.0)
    avg_tpr = sum(tprs) / len(tprs)
    avg_fpr = sum(fprs) / len(fprs)
    avg_score = avg_tpr - avg_fpr
    print(f"\nOverall Results (metodologia oficial OWASP, promedio simple por categoria):")
    print(f"  TPR promedio = {avg_tpr:.2%}   FPR promedio = {avg_fpr:.2%}   Score = {avg_score:.2%}")

    print("\nUnmapped check_ids (no deberian existir si el mapeo esta completo):", dict(unmapped))
    print("Total test cases en expectedresults:", len(expected))
    print("Total (test_name, category) flags reales de Semgrep:", len(flagged))

    return rows_for_md, (precision, recall, fpr, tp, fp, tn, fn, sum(overall.values())), (avg_tpr, avg_fpr, avg_score)


if __name__ == "__main__":
    score()
