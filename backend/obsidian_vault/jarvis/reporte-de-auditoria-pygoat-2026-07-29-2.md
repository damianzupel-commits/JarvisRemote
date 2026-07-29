---
author: jarvis
created: '2026-07-29T02:03:30.916973+00:00'
tags:
- reportes
- auditoria
- seguridad
- calidad
title: Reporte de auditoría -- pygoat -- 2026-07-29
updated: '2026-07-29T02:03:30.916973+00:00'
---

# Reporte de auditoría de código -- pygoat

- Proyecto: `C:\Users\dam\Documents\test-scans\pygoat`
- Generado: 2026-07-29T02:03:30.916973+00:00
- Último escaneo de seguridad: 2026-07-29T02:03:25.828404+00:00 (corrieron: semgrep, bandit, trivy)
- Último escaneo de calidad: 2026-07-29T02:03:30.882941+00:00 (corrieron: ruff, mypy, eslint)

## Resumen ejecutivo

347 hallazgo(s) de seguridad real(es) (9 crítico(s), 78 alto(s)). 87 hallazgo(s) de calidad (38 de severidad 'alta' según el propio analizador -- es la clasificación de Ruff/mypy, no un nivel de riesgo de seguridad).

## Hallazgos de seguridad (347)

| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |
|---|---|---|---|---|
| critical | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2023-31047` (trivy) | django 3.2.18: python-django: Potential bypass of validation when uploading multiple files using one form field (fix: 3.2.19, 4.1.9, 4.2.1) |
| critical | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2025-64459` (trivy) | django 3.2.18: django: Django SQL injection (fix: 5.2.8, 5.1.14, 4.2.26) |
| critical | `requirements.txt` | 1 | `CVE-2023-31047` (trivy) | Django 4.2: python-django: Potential bypass of validation when uploading multiple files using one form field (fix: 3.2.19, 4.1.9, 4.2.1) |
| critical | `requirements.txt` | 1 | `CVE-2024-42005` (trivy) | Django 4.2: python-django: Potential SQL injection in QuerySet.values() and values_list() (fix: 5.0.8, 4.2.15) |
| critical | `requirements.txt` | 1 | `CVE-2025-64459` (trivy) | Django 4.2: django: Django SQL injection (fix: 5.2.8, 5.1.14, 4.2.26) |
| critical | `requirements.txt` | 1 | `CVE-2023-50447` (trivy) | Pillow 9.4.0: pillow: Arbitrary Code Execution via the environment parameter (fix: 10.2.0) |
| critical | `requirements.txt` | 1 | `CVE-2019-20477` (trivy) | PyYAML 5.1: PyYAML: command execution through python/object/apply constructor in FullLoader (fix: 5.2) |
| critical | `requirements.txt` | 1 | `CVE-2020-14343` (trivy) | PyYAML 5.1: PyYAML: incomplete fix for CVE-2020-1747 (fix: 5.4) |
| critical | `requirements.txt` | 1 | `CVE-2020-1747` (trivy) | PyYAML 5.1: PyYAML: arbitrary command execution through python/object/new when FullLoader is used (fix: 5.3.1) |
| high | `Dockerfile` | 33 | `dockerfile.security.missing-user.missing-user` (semgrep) | By not specifying a USER, a program in the container may run as 'root'. This is a security hazard. If an attacker can control a process running as root, they ma |
| high | `challenge/views.py` | 81 | `python.django.security.injection.command.subprocess-injection.subprocess-injection` (semgrep) | Detected user input entering a `subprocess` call unsafely. This could result in a command injection vulnerability. An attacker could use this vulnerability to e |
| high | `dockerized_labs/broken_auth_lab/Dockerfile` | 21 | `dockerfile.security.missing-user.missing-user` (semgrep) | By not specifying a USER, a program in the container may run as 'root'. This is a security hazard. If an attacker can control a process running as root, they ma |
| high | `dockerized_labs/broken_auth_lab/app.py` | 86 | `B324` (bandit) | Use of weak MD5 hash for security. Consider usedforsecurity=False |
| high | `dockerized_labs/broken_auth_lab/app.py` | 123 | `B201` (bandit) | A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger and allows the execution of arbitrary code. |
| high | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2024-34069` (trivy) | Werkzeug 2.3.7: python-werkzeug: user may execute code on a developer's machine (fix: 3.0.3) |
| high | `dockerized_labs/insec_des_lab/Dockerfile` | 15 | `dockerfile.security.missing-user.missing-user` (semgrep) | By not specifying a USER, a program in the container may run as 'root'. This is a security hazard. If an attacker can control a process running as root, they ma |
| high | `dockerized_labs/insec_des_lab/main.py` | 27 | `python.flask.security.insecure-deserialization.insecure-deserialization` (semgrep) | Detected the use of an insecure deserialization library in a Flask route. These libraries are prone to code execution vulnerabilities. Ensure user data does not |
| high | `dockerized_labs/insec_des_lab/main.py` | 36 | `python.flask.security.insecure-deserialization.insecure-deserialization` (semgrep) | Detected the use of an insecure deserialization library in a Flask route. These libraries are prone to code execution vulnerabilities. Ensure user data does not |
| high | `dockerized_labs/insec_des_lab/requirements.txt` | 1 | `CVE-2024-34069` (trivy) | Werkzeug 3.0.1: python-werkzeug: user may execute code on a developer's machine (fix: 3.0.3) |
| high | `dockerized_labs/sensitive_data_exposure/Dockerfile` | 18 | `dockerfile.security.missing-user-entrypoint.missing-user-entrypoint` (semgrep) | By not specifying a USER, a program in the container may run as 'root'. This is a security hazard. If an attacker can control a process running as root, they ma |
| high | `dockerized_labs/sensitive_data_exposure/Dockerfile` | 19 | `dockerfile.security.missing-user.missing-user` (semgrep) | By not specifying a USER, a program in the container may run as 'root'. This is a security hazard. If an attacker can control a process running as root, they ma |
| high | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2023-36053` (trivy) | django 3.2.18: python-django: Potential regular expression denial of service vulnerability in EmailValidator/URLValidator (fix: 3.2.20, 4.1.10, 4.2.3) |
| high | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2023-43665` (trivy) | django 3.2.18: python-django: Denial-of-service possibility in django.utils.text.Truncator (fix: 3.2.22, 4.1.12, 4.2.6) |
| high | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2023-46695` (trivy) | django 3.2.18: python-django: Potential denial of service vulnerability in UsernameField on Windows (fix: 3.2.23, 4.1.13, 4.2.7) |
| high | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2024-24680` (trivy) | django 3.2.18: Django: denial-of-service in ``intcomma`` template filter (fix: 3.2.24, 4.2.10, 5.0.2) |
| high | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2025-57833` (trivy) | django 3.2.18: django: Django SQL injection in FilteredRelation column aliases (fix: 4.2.24, 5.1.12, 5.2.6) |
| high | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2025-64458` (trivy) | django 3.2.18: Django: Denial-of-service vulnerability in Django on Windows (fix: 5.2.8, 5.1.14, 4.2.26) |
| high | `introduction/mitre.py` | 161 | `B324` (bandit) | Use of weak MD5 hash for security. Consider usedforsecurity=False |
| high | `introduction/mitre.py` | 169 | `python.jwt.security.jwt-hardcode.jwt-python-hardcoded-secret` (semgrep) | Hardcoded JWT secret or private key is used. This is a Insufficiently Protected Credentials weakness: https://cwe.mitre.org/data/definitions/522.html Consider u |
| high | `introduction/mitre.py` | 233 | `python.lang.security.audit.subprocess-shell-true.subprocess-shell-true` (semgrep) | Found 'subprocess' function 'Popen' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates cur |
| high | `introduction/mitre.py` | 233 | `B602` (bandit) | subprocess call with shell=True identified, security issue. |
| high | `introduction/static/js/a7.js` | 4 | `generic.secrets.security.detected-jwt-token.detected-jwt-token` (semgrep) | JWT token detected |
| high | `introduction/static/js/a9.js` | 18 | `generic.secrets.security.detected-jwt-token.detected-jwt-token` (semgrep) | JWT token detected |
| high | `introduction/views.py` | 158 | `python.django.security.injection.tainted-sql-string.tainted-sql-string` (semgrep) | Detected user input used to manually construct a SQL string. This is usually bad practice because manual construction could accidentally result in a SQL injecti |
| high | `introduction/views.py` | 214 | `python.django.security.audit.avoid-insecure-deserialization.avoid-insecure-deserialization` (semgrep) | Avoid using insecure deserialization library, backed by `pickle`, `_pickle`, `cpickle`, `dill`, `shelve`, or `yaml`, which are known to lead to remote code exec |
| high | `introduction/views.py` | 430 | `python.django.security.injection.command.subprocess-injection.subprocess-injection` (semgrep) | Detected user input entering a `subprocess` call unsafely. This could result in a command injection vulnerability. An attacker could use this vulnerability to e |
| high | `introduction/views.py` | 431 | `python.lang.security.dangerous-subprocess-use.dangerous-subprocess-use` (semgrep) | Detected subprocess function 'cmd_lab' with user controlled data. A malicious actor could leverage this to perform command injection. You may consider using 'sh |
| high | `introduction/views.py` | 432 | `python.lang.security.audit.subprocess-shell-true.subprocess-shell-true` (semgrep) | Found 'subprocess' function 'Popen' with 'shell=True'. This is dangerous because this call will spawn the command using a shell process. Doing so propagates cur |
| high | `introduction/views.py` | 432 | `B602` (bandit) | subprocess call with shell=True identified, security issue. |
| high | `introduction/views.py` | 560 | `python.django.security.audit.avoid-insecure-deserialization.avoid-insecure-deserialization` (semgrep) | Avoid using insecure deserialization library, backed by `pickle`, `_pickle`, `cpickle`, `dill`, `shelve`, or `yaml`, which are known to lead to remote code exec |
| high | `introduction/views.py` | 864 | `python.django.security.injection.tainted-sql-string.tainted-sql-string` (semgrep) | Detected user input used to manually construct a SQL string. This is usually bad practice because manual construction could accidentally result in a SQL injecti |
| high | `introduction/views.py` | 961 | `python.django.security.injection.ssrf.ssrf-injection-requests.ssrf-injection-requests` (semgrep) | Data from request object is passed to a new server-side request. This could lead to a server-side request forgery (SSRF). To mitigate, ensure that schemes and h |
| high | `introduction/views.py` | 1026 | `B324` (bandit) | Use of weak MD5 hash for security. Consider usedforsecurity=False |
| high | `requirements.txt` | 1 | `CVE-2023-36053` (trivy) | Django 4.2: python-django: Potential regular expression denial of service vulnerability in EmailValidator/URLValidator (fix: 3.2.20, 4.1.10, 4.2.3) |
| high | `requirements.txt` | 1 | `CVE-2023-43665` (trivy) | Django 4.2: python-django: Denial-of-service possibility in django.utils.text.Truncator (fix: 3.2.22, 4.1.12, 4.2.6) |
| high | `requirements.txt` | 1 | `CVE-2023-46695` (trivy) | Django 4.2: python-django: Potential denial of service vulnerability in UsernameField on Windows (fix: 3.2.23, 4.1.13, 4.2.7) |
| high | `requirements.txt` | 1 | `CVE-2024-24680` (trivy) | Django 4.2: Django: denial-of-service in ``intcomma`` template filter (fix: 3.2.24, 4.2.10, 5.0.2) |
| high | `requirements.txt` | 1 | `CVE-2024-38875` (trivy) | Django 4.2: python-django: Potential denial-of-service in django.utils.html.urlize() (fix: 4.2.14, 5.0.7) |
| high | `requirements.txt` | 1 | `CVE-2024-39330` (trivy) | Django 4.2: python-django: Potential directory-traversal in django.core.files.storage.Storage.save() (fix: 5.0.7, 4.2.14) |
| high | `requirements.txt` | 1 | `CVE-2024-39614` (trivy) | Django 4.2: python-django: Potential denial-of-service in django.utils.translation.get_supported_language_variant() (fix: 5.0.7, 4.2.14) |
| high | `requirements.txt` | 1 | `CVE-2024-53908` (trivy) | Django 4.2: django: Potential SQL injection in HasKey(lhs, rhs) on Oracle (fix: 5.0.10, 5.1.4, 4.2.17) |
| high | `requirements.txt` | 1 | `CVE-2025-57833` (trivy) | Django 4.2: django: Django SQL injection in FilteredRelation column aliases (fix: 4.2.24, 5.1.12, 5.2.6) |
| high | `requirements.txt` | 1 | `CVE-2025-59681` (trivy) | Django 4.2: django: Potential SQL injection in QuerySet.annotate(), alias(), aggregate(), and extra() on MySQL and MariaDB1 (fix: 4.2.25, 5.1.13, 5.2.7) |
| high | `requirements.txt` | 1 | `CVE-2025-64458` (trivy) | Django 4.2: Django: Denial-of-service vulnerability in Django on Windows (fix: 5.2.8, 5.1.14, 4.2.26) |
| high | `requirements.txt` | 1 | `CVE-2026-1207` (trivy) | Django 4.2: Django: Django: SQL Injection via RasterField band index parameter (fix: 6.0.2, 5.2.11, 4.2.28) |
| high | `requirements.txt` | 1 | `CVE-2026-1287` (trivy) | Django 4.2: Django: Django: SQL Injection via crafted column aliases (fix: 6.0.2, 5.2.11, 4.2.28) |
| high | `requirements.txt` | 1 | `CVE-2026-25673` (trivy) | Django 4.2: django: Django: Denial of Service via slow URL normalization on Windows (fix: 6.0.3, 5.2.12, 4.2.29) |
| high | `requirements.txt` | 1 | `CVE-2026-33034` (trivy) | Django 4.2: Django: Django: Denial of Service via missing or understated Content-Length header in ASGI requests (fix: 6.0.4, 5.2.13, 4.2.30) |
| high | `requirements.txt` | 1 | `CVE-2026-3902` (trivy) | Django 4.2: Django: Django: Header spoofing via ambiguous header mapping (fix: 6.0.4, 5.2.13, 4.2.30) |
| high | `requirements.txt` | 1 | `CVE-2023-44271` (trivy) | Pillow 9.4.0: python-pillow: uncontrolled resource consumption when textlength in an ImageDraw instance operates on a long text argument (fix: 10.0.0) |
| high | `requirements.txt` | 1 | `CVE-2023-4863` (trivy) | Pillow 9.4.0: libwebp: Heap buffer overflow in WebP Codec (fix: 10.0.1) |
| high | `requirements.txt` | 1 | `CVE-2024-28219` (trivy) | Pillow 9.4.0: python-pillow: buffer overflow in _imagingcms.c (fix: 10.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-54058` (trivy) | Pillow 9.4.0: Pillow: Pillow: Memory disclosure or denial of service via crafted McIdas AREA image (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-54059` (trivy) | Pillow 9.4.0: python-pillow: Pillow: Denial of Service via crafted PCF font data (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-54060` (trivy) | Pillow 9.4.0: python-pillow: Pillow: Denial of Service via excessive memory allocation when processing font files (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-55379` (trivy) | Pillow 9.4.0: python-pillow: Pillow: Denial of Service via crafted BDF font file (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-55380` (trivy) | Pillow 9.4.0: python-pillow: Pillow: Denial of Service via crafted GD 2.x image file (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-59197` (trivy) | Pillow 9.4.0: Pillow: Pillow: Native heap out-of-bounds write (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-59199` (trivy) | Pillow 9.4.0: Pillow: Pillow: Denial of Service via out-of-bounds write in image processing (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-59200` (trivy) | Pillow 9.4.0: Pillow: Pillow: Denial of service via crafted PDF stream (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-59204` (trivy) | Pillow 9.4.0: Pillow: Pillow: Denial of Service via crafted JPEG2000 image (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-59205` (trivy) | Pillow 9.4.0: Pillow: Pillow: Controlled native heap corruption in ImageCms.ImageCmsTransform.apply API (fix: 12.3.0) |
| high | `requirements.txt` | 1 | `CVE-2026-32597` (trivy) | PyJWT 2.4.0: pyjwt: PyJWT accepts unknown `crit` header extensions (RFC 7515 Â§4.1.11 MUST violation) (fix: 2.12.0) |
| high | `requirements.txt` | 1 | `CVE-2026-48526` (trivy) | PyJWT 2.4.0: python-pyjwt: PyJWT: Authentication bypass due to forged JSON Web Tokens (fix: 2.13.0) |
| high | `requirements.txt` | 1 | `CVE-2023-25577` (trivy) | Werkzeug 2.1.2: python-werkzeug: high resource usage when parsing multipart form data with many fields (fix: 2.2.3) |
| high | `requirements.txt` | 1 | `CVE-2024-34069` (trivy) | Werkzeug 2.1.2: python-werkzeug: user may execute code on a developer's machine (fix: 3.0.3) |
| high | `requirements.txt` | 1 | `CVE-2023-37920` (trivy) | certifi 2022.12.7: python-certifi: Removal of e-Tugra root certificate (fix: 2023.7.22) |
| high | `requirements.txt` | 1 | `CVE-2023-50782` (trivy) | cryptography 39.0.1: python-cryptography: Bleichenbacher timing oracle attack against RSA decryption - incomplete fix for CVE-2020-25659 (fix: 42.0.0) |
| high | `requirements.txt` | 1 | `CVE-2024-26130` (trivy) | cryptography 39.0.1: python-cryptography: NULL pointer dereference with pkcs12.serialize_key_and_certificates when called with a non-matching certificate and pr |
| high | `requirements.txt` | 1 | `CVE-2026-26007` (trivy) | cryptography 39.0.1: cryptography: cryptography Subgroup Attack Due to Missing Subgroup Validation for SECT Curves (fix: 46.0.5) |
| high | `requirements.txt` | 1 | `GHSA-537c-gmf6-5ccf` (trivy) | cryptography 39.0.1: Vulnerable OpenSSL included in cryptography wheels (fix: 48.0.1) |
| high | `requirements.txt` | 1 | `CVE-2024-4340` (trivy) | sqlparse 0.3.1: sqlparse: parsing heavily nested list leads to denial of service (fix: 0.5.0) |
| high | `requirements.txt` | 1 | `CVE-2023-43804` (trivy) | urllib3 1.26.9: python-urllib3: Cookie request header isn't stripped during cross-origin redirects (fix: 2.0.6, 1.26.17) |
| high | `requirements.txt` | 1 | `CVE-2025-66418` (trivy) | urllib3 1.26.9: urllib3: urllib3: Unbounded decompression chain leads to resource exhaustion (fix: 2.6.0) |
| high | `requirements.txt` | 1 | `CVE-2025-66471` (trivy) | urllib3 1.26.9: urllib3: urllib3 Streaming API improperly handles highly compressed data (fix: 2.6.0) |
| high | `requirements.txt` | 1 | `CVE-2026-21441` (trivy) | urllib3 1.26.9: urllib3: urllib3 vulnerable to decompression-bomb safeguard bypass when following HTTP redirects (streaming API) (fix: 2.6.3) |
| high | `requirements.txt` | 1 | `CVE-2026-44431` (trivy) | urllib3 1.26.9: urllib3: urllib3: Information disclosure via cross-origin redirects forwarding sensitive headers (fix: 2.7.0) |
| medium | `.github/workflows/flake8.yml` | 18 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `.github/workflows/flake8.yml` | 20 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `.github/workflows/hadolint.yml` | 30 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `dockerized_labs/broken_auth_lab/app.py` | 49 | `python.flask.security.audit.secure-set-cookie.secure-set-cookie` (semgrep) | Found a Flask cookie with insecurely configured properties.  By default the secure, httponly and samesite ar configured insecurely. cookies should be handled se |
| medium | `dockerized_labs/broken_auth_lab/app.py` | 51 | `python.flask.security.audit.secure-set-cookie.secure-set-cookie` (semgrep) | Found a Flask cookie with insecurely configured properties.  By default the secure, httponly and samesite ar configured insecurely. cookies should be handled se |
| medium | `dockerized_labs/broken_auth_lab/app.py` | 123 | `python.flask.security.audit.app-run-param-config.avoid_app_run_with_bad_host` (semgrep) | Running flask app with host 0.0.0.0 could expose the server publicly. |
| medium | `dockerized_labs/broken_auth_lab/app.py` | 123 | `python.flask.security.audit.debug-enabled.debug-enabled` (semgrep) | Detected Flask app with debug=True. Do not deploy to production with this flag enabled as it will leak sensitive information. Instead, consider using Flask conf |
| medium | `dockerized_labs/broken_auth_lab/app.py` | 123 | `B104` (bandit) | Possible binding to all interfaces. |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2024-22195` (trivy) | Jinja2 3.1.2: jinja2: HTML attribute injection when passing user input as keys to xmlattr filter (fix: 3.1.3) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2024-34064` (trivy) | Jinja2 3.1.2: jinja2: accepts keys containing non-attribute characters (fix: 3.1.4) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2024-56201` (trivy) | Jinja2 3.1.2: jinja2: Jinja has a sandbox breakout through malicious filenames (fix: 3.1.5) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2024-56326` (trivy) | Jinja2 3.1.2: jinja2: Jinja has a sandbox breakout through indirect reference to format method (fix: 3.1.5) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2025-27516` (trivy) | Jinja2 3.1.2: jinja2: Jinja sandbox breakout through attr filter selecting format method (fix: 3.1.6) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2023-46136` (trivy) | Werkzeug 2.3.7: python-werkzeug: high resource consumption leading to denial of service (fix: 3.0.1, 2.3.8) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2024-49766` (trivy) | Werkzeug 2.3.7: werkzeug: python-werkzeug: Werkzeug safe_join not safe on Windows (fix: 3.0.6) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2024-49767` (trivy) | Werkzeug 2.3.7: werkzeug: python-werkzeug: Werkzeug possible resource exhaustion when parsing file data in forms (fix: 3.0.6) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2025-66221` (trivy) | Werkzeug 2.3.7: Werkzeug: Werkzeug: Denial of service via Windows device names in path segments (fix: 3.1.4) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2026-21860` (trivy) | Werkzeug 2.3.7:  Werkzeug safe_join() allows Windows special device names with compound extensions (fix: 3.1.5) |
| medium | `dockerized_labs/broken_auth_lab/requirements.txt` | 1 | `CVE-2026-27199` (trivy) | Werkzeug 2.3.7:  Werkzeug safe_join() allows Windows special device names (fix: 3.1.6) |
| medium | `dockerized_labs/broken_auth_lab/templates/lab.html` | 13 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `dockerized_labs/broken_auth_lab/templates/lab.html` | 29 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `dockerized_labs/broken_auth_lab/templates/lab.html` | 40 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `dockerized_labs/broken_auth_lab/templates/reset.html` | 13 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `dockerized_labs/insec_des_lab/main.py` | 27 | `python.lang.security.deserialization.pickle.avoid-pickle` (semgrep) | Avoid using `pickle`, which is known to lead to code execution vulnerabilities. When unpickling, the serialized data could be manipulated to run arbitrary code. |
| medium | `dockerized_labs/insec_des_lab/main.py` | 36 | `python.lang.security.deserialization.pickle.avoid-pickle` (semgrep) | Avoid using `pickle`, which is known to lead to code execution vulnerabilities. When unpickling, the serialized data could be manipulated to run arbitrary code. |
| medium | `dockerized_labs/insec_des_lab/main.py` | 36 | `B301` (bandit) | Pickle and modules that wrap it can be unsafe when used to deserialize untrusted data, possible security issue. |
| medium | `dockerized_labs/insec_des_lab/main.py` | 51 | `python.flask.security.audit.app-run-param-config.avoid_app_run_with_bad_host` (semgrep) | Running flask app with host 0.0.0.0 could expose the server publicly. |
| medium | `dockerized_labs/insec_des_lab/main.py` | 51 | `B104` (bandit) | Possible binding to all interfaces. |
| medium | `dockerized_labs/insec_des_lab/requirements.txt` | 1 | `CVE-2024-49766` (trivy) | Werkzeug 3.0.1: werkzeug: python-werkzeug: Werkzeug safe_join not safe on Windows (fix: 3.0.6) |
| medium | `dockerized_labs/insec_des_lab/requirements.txt` | 1 | `CVE-2024-49767` (trivy) | Werkzeug 3.0.1: werkzeug: python-werkzeug: Werkzeug possible resource exhaustion when parsing file data in forms (fix: 3.0.6) |
| medium | `dockerized_labs/insec_des_lab/requirements.txt` | 1 | `CVE-2025-66221` (trivy) | Werkzeug 3.0.1: Werkzeug: Werkzeug: Denial of service via Windows device names in path segments (fix: 3.1.4) |
| medium | `dockerized_labs/insec_des_lab/requirements.txt` | 1 | `CVE-2026-21860` (trivy) | Werkzeug 3.0.1:  Werkzeug safe_join() allows Windows special device names with compound extensions (fix: 3.1.5) |
| medium | `dockerized_labs/insec_des_lab/requirements.txt` | 1 | `CVE-2026-27199` (trivy) | Werkzeug 3.0.1:  Werkzeug safe_join() allows Windows special device names (fix: 3.1.6) |
| medium | `dockerized_labs/insec_des_lab/templates/index.html` | 61 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `dockerized_labs/insec_des_lab/templates/index.html` | 69 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2023-41164` (trivy) | django 3.2.18: python-django: Potential denial of service vulnerability in  ``django.utils.encoding.uri_to_iri()`` (fix: 3.2.21, 4.1.11, 4.2.5) |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2024-27351` (trivy) | django 3.2.18: python-django: Potential regular expression denial-of-service in django.utils.text.Truncator.words() (fix: 3.2.25, 4.2.11, 5.0.3) |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2024-45231` (trivy) | django 3.2.18: python-django: Potential user email enumeration via response status on password reset (fix: 5.1.1, 5.0.9, 4.2.16) |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2025-48432` (trivy) | django 3.2.18: django: Django Path Injection Vulnerability (fix: 5.2.2, 5.1.10, 4.2.22) |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2023-32681` (trivy) | requests 2.28.1: python-requests: Unintended leak of Proxy-Authorization header (fix: 2.31.0) |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2024-35195` (trivy) | requests 2.28.1: requests: subsequent requests to the same host ignore cert verification (fix: 2.32.0) |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2024-47081` (trivy) | requests 2.28.1: requests: Requests vulnerable to .netrc credentials leak via malicious URLs (fix: 2.32.4) |
| medium | `dockerized_labs/sensitive_data_exposure/requirements.txt` | 1 | `CVE-2026-25645` (trivy) | requests 2.28.1: requests: Requests: Security bypass due to predictable temporary file creation (fix: 2.33.0) |
| medium | `dockerized_labs/sensitive_data_exposure/templates/about.html` | 5 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/about.html` | 91 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/about.html` | 92 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/about.html` | 93 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/base.html` | 5 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/base.html` | 60 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/base.html` | 61 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/base.html` | 62 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/index.html` | 5 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/index.html` | 132 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/index.html` | 133 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/index.html` | 134 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/lesson.html` | 5 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/lesson.html` | 337 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/lesson.html` | 338 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/lesson.html` | 339 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/lesson.html` | 340 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/login.html` | 5 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/login.html` | 54 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `dockerized_labs/sensitive_data_exposure/templates/login.html` | 82 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/login.html` | 83 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/login.html` | 84 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/profile.html` | 5 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/profile.html` | 211 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/profile.html` | 212 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/profile.html` | 213 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/profile.html` | 214 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/register.html` | 5 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/register.html` | 93 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/register.html` | 94 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `dockerized_labs/sensitive_data_exposure/templates/register.html` | 95 | `html.security.audit.missing-integrity.missing-integrity` (semgrep) | This tag is missing an 'integrity' subresource integrity attribute. The 'integrity' attribute allows for the browser to verify that externally hosted files (for |
| medium | `introduction/apis.py` | 22 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/apis.py` | 59 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/apis.py` | 64 | `python.django.security.injection.request-data-write.request-data-write` (semgrep) | Found user-controlled request data passed into '.write(...)'. This could be dangerous if a malicious actor is able to control data into sensitive files. For exa |
| medium | `introduction/apis.py` | 65 | `python.django.security.injection.request-data-write.request-data-write` (semgrep) | Found user-controlled request data passed into '.write(...)'. This could be dangerous if a malicious actor is able to control data into sensitive files. For exa |
| medium | `introduction/apis.py` | 93 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/apis.py` | 112 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/apis.py` | 125 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/apis.py` | 130 | `python.django.security.injection.request-data-write.request-data-write` (semgrep) | Found user-controlled request data passed into '.write(...)'. This could be dangerous if a malicious actor is able to control data into sensitive files. For exa |
| medium | `introduction/lab_code/test.py` | 23 | `B506` (bandit) | Use of unsafe yaml load. Allows instantiation of arbitrary objects. Consider yaml.safe_load(). |
| medium | `introduction/mitre.py` | 161 | `python.lang.security.audit.md5-used-as-password.md5-used-as-password` (semgrep) | It looks like MD5 is used as a password hash. MD5 is not considered a secure password hash because it can be cracked by an attacker in a short amount of time. U |
| medium | `introduction/mitre.py` | 171 | `python.django.security.audit.secure-cookies.django-secure-set-cookie` (semgrep) | Django cookies should be handled securely by setting secure=True, httponly=True, and samesite='Lax' in response.set_cookie(...). If your situation calls for dif |
| medium | `introduction/mitre.py` | 176 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/mitre.py` | 214 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/mitre.py` | 217 | `python.django.security.injection.code.user-eval.user-eval` (semgrep) | Found user data in a call to 'eval'. This is extremely dangerous because it can enable an attacker to execute arbitrary remote code on the system. Instead, refa |
| medium | `introduction/mitre.py` | 218 | `python.lang.security.audit.eval-detected.eval-detected` (semgrep) | Detected the use of eval(). eval() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a co |
| medium | `introduction/mitre.py` | 218 | `B307` (bandit) | Use of possibly insecure function - consider using safer ast.literal_eval. |
| medium | `introduction/mitre.py` | 237 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/playground/A6/soln.py` | 9 | `B113` (bandit) | Call to requests without timeout |
| medium | `introduction/playground/A6/utility.py` | 9 | `B113` (bandit) | Call to requests without timeout |
| medium | `introduction/playground/A9/api.py` | 7 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/playground/A9/archive.py` | 7 | `python.django.security.audit.csrf-exempt.no-csrf-exempt` (semgrep) | Detected usage of @csrf_exempt, which indicates that there is no CSRF token set for this route. This could lead to an attacker manipulating the user's account a |
| medium | `introduction/templates/Lab/A9/a9_lab.html` | 10 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/A9/a9_lab2.html` | 21 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/BrokenAccess/ba_lab.html` | 11 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/BrokenAuth/otp.html` | 18 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/CMD/cmd_lab.html` | 9 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/CMD/cmd_lab2.html` | 9 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/ssrf/ssrf_discussion.html` | 125 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/ssrf/ssrf_discussion.html` | 130 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/ssrf/ssrf_discussion.html` | 135 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab/ssrf/ssrf_discussion.html` | 140 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab_2021/A1_BrokenAccessControl/broken_access_lab_1.html` | 11 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/templates/Lab_2021/A1_BrokenAccessControl/broken_access_lab_2.html` | 11 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `introduction/views.py` | 158 | `B608` (bandit) | Possible SQL injection vector through string-based query construction. |
| medium | `introduction/views.py` | 162 | `python.django.security.audit.raw-query.avoid-raw-sql` (semgrep) | Detected the use of 'RawSQL' or 'raw' indicating the execution of a non-parameterized SQL query. This could lead to a SQL injection and therefore protected info |
| medium | `introduction/views.py` | 202 | `python.lang.security.deserialization.pickle.avoid-pickle` (semgrep) | Avoid using `pickle`, which is known to lead to code execution vulnerabilities. When unpickling, the serialized data could be manipulated to run arbitrary code. |
| medium | `introduction/views.py` | 211 | `python.django.security.audit.secure-cookies.django-secure-set-cookie` (semgrep) | Django cookies should be handled securely by setting secure=True, httponly=True, and samesite='Lax' in response.set_cookie(...). If your situation calls for dif |
| medium | `introduction/views.py` | 214 | `python.lang.security.deserialization.pickle.avoid-pickle` (semgrep) | Avoid using `pickle`, which is known to lead to code execution vulnerabilities. When unpickling, the serialized data could be manipulated to run arbitrary code. |
| medium | `introduction/views.py` | 214 | `B301` (bandit) | Pickle and modules that wrap it can be unsafe when used to deserialize untrusted data, possible security issue. |

_(+147 más, omitidos por espacio)_

## Hallazgos de calidad (87)

| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |
|---|---|---|---|---|
| high | `dockerized_labs/broken_auth_lab/app.py` | 25 | `var-annotated` (mypy) | Need type annotation for "password_reset_tokens" (hint: "password_reset_tokens: dict[<type>, <type>] = ...") |
| high | `introduction/migrations/0001_initial.py` | 10 | `var-annotated` (mypy) | Need type annotation for "dependencies" (hint: "dependencies: list[<type>] = ...") |
| high | `introduction/playground/A9/archive.py` | 42 | `no-redef` (mypy) | Name "Log" already defined (possibly by an import) |
| high | `introduction/static/Lab/ssrf.js` | 2 | `no-unused-vars` (eslint) | 'frame1to2' is defined but never used. |
| high | `introduction/static/Lab/ssrf.js` | 9 | `no-unused-vars` (eslint) | 'frame2to3' is defined but never used. |
| high | `introduction/static/Lab/ssrf.js` | 28 | `no-undef` (eslint) | 'alert' is not defined. |
| high | `introduction/static/Lab/ssrf.js` | 33 | `no-unused-vars` (eslint) | 'frame3to4' is defined but never used. |
| high | `introduction/static/Lab/ssrf.js` | 52 | `no-undef` (eslint) | 'alert' is not defined. |
| high | `introduction/static/Lab/ssrf.js` | 58 | `no-unused-vars` (eslint) | 'checkcode' is defined but never used. |
| high | `introduction/static/Lab/ssrf.js` | 62 | `no-undef` (eslint) | 'FormData' is not defined. |
| high | `introduction/static/Lab/ssrf.js` | 71 | `no-undef` (eslint) | 'fetch' is not defined. |
| high | `introduction/static/Lab/ssrf.js` | 76 | `no-undef` (eslint) | 'alert' is not defined. |
| high | `introduction/static/Lab/xss.js` | 27 | `no-unused-vars` (eslint) | 'SendToServer' is defined but never used. |
| high | `introduction/static/Lab/xss.js` | 29 | `no-undef` (eslint) | 'comment' is not defined. |
| high | `introduction/static/Lab/xss.js` | 33 | `no-undef` (eslint) | 'XMLHttpRequest' is not defined. |
| high | `introduction/static/Lab/xss.js` | 34 | `no-undef` (eslint) | 'xml' is not defined. |
| high | `introduction/static/Lab/xss.js` | 34 | `no-undef` (eslint) | 'comment' is not defined. |
| high | `introduction/static/Lab/xss.js` | 35 | `no-undef` (eslint) | '$' is not defined. |
| high | `introduction/static/Lab/xss.js` | 38 | `no-undef` (eslint) | 'xml' is not defined. |
| high | `introduction/static/js/a6.js` | 1 | `no-undef` (eslint) | 'event5' is not defined. |
| high | `introduction/static/js/a6.js` | 3 | `no-undef` (eslint) | 'Headers' is not defined. |
| high | `introduction/static/js/a6.js` | 4 | `no-undef` (eslint) | 'FormData' is not defined. |
| high | `introduction/static/js/a6.js` | 13 | `no-undef` (eslint) | 'fetch' is not defined. |
| high | `introduction/static/js/a6.js` | 18 | `no-undef` (eslint) | 'alert' is not defined. |
| high | `introduction/static/js/a6.js` | 24 | `no-undef` (eslint) | 'event6' is not defined. |
| high | `introduction/static/js/a6.js` | 26 | `no-undef` (eslint) | 'Headers' is not defined. |
| high | `introduction/static/js/a6.js` | 27 | `no-undef` (eslint) | 'FormData' is not defined. |
| high | `introduction/static/js/a6.js` | 36 | `no-undef` (eslint) | 'fetch' is not defined. |
| high | `introduction/static/js/a7.js` | 1 | `no-undef` (eslint) | 'event4' is not defined. |
| high | `introduction/static/js/a7.js` | 3 | `no-undef` (eslint) | 'Headers' is not defined. |
| high | `introduction/static/js/a7.js` | 6 | `no-undef` (eslint) | 'FormData' is not defined. |
| high | `introduction/static/js/a7.js` | 17 | `no-undef` (eslint) | 'fetch' is not defined. |
| high | `introduction/static/js/a9.js` | 3 | `no-undef` (eslint) | 'event1' is not defined. |
| high | `introduction/static/js/a9.js` | 8 | `no-undef` (eslint) | 'event2' is not defined. |
| high | `introduction/static/js/a9.js` | 13 | `no-undef` (eslint) | 'event3' is not defined. |
| high | `introduction/static/js/a9.js` | 17 | `no-undef` (eslint) | 'Headers' is not defined. |
| high | `introduction/static/js/a9.js` | 20 | `no-undef` (eslint) | 'FormData' is not defined. |
| high | `introduction/static/js/a9.js` | 32 | `no-undef` (eslint) | 'fetch' is not defined. |
| medium | `challenge/management/commands/populate_challenge.py` | 20 | `B904` (ruff) | Within an `except` clause, raise exceptions with `raise ... from err` or `raise ... from None` to distinguish them from errors in exception handling |
| medium | `introduction/views.py` | 704 | `B007` (ruff) | Loop control variable `i` not used within loop body |
| low | `PyGoatBot.py` | 2 | `F401` (ruff) | `chatterbot.logic.BestMatch` imported but unused |
| low | `challenge/tests.py` | 1 | `F401` (ruff) | `django.test.TestCase` imported but unused |
| low | `challenge/urls.py` | 1 | `F401` (ruff) | `django.urls.include` imported but unused |
| low | `challenge/urls.py` | 2 | `F403` (ruff) | `from .views import *` used; unable to detect undefined names |
| low | `challenge/urls.py` | 5 | `F405` (ruff) | `DoItFast` may be undefined, or defined from star imports |
| low | `challenge/views.py` | 4 | `F401` (ruff) | `django.views.decorators.csrf.csrf_exempt` imported but unused |
| low | `challenge/views.py` | 18 | `F841` (ruff) | Local variable `e` is assigned to but never used |
| low | `challenge/views.py` | 34 | `F841` (ruff) | Local variable `e` is assigned to but never used |
| low | `challenge/views.py` | 75 | `F841` (ruff) | Local variable `e` is assigned to but never used |
| low | `dockerized_labs/broken_auth_lab/app.py` | 3 | `F401` (ruff) | `json` imported but unused |
| low | `dockerized_labs/broken_auth_lab/app.py` | 4 | `F401` (ruff) | `datetime.timedelta` imported but unused |
| low | `dockerized_labs/insec_des_lab/main.py` | 1 | `F401` (ruff) | `flask.make_response` imported but unused |
| low | `introduction/apis.py` | 1 | `F401` (ruff) | `time` imported but unused |
| low | `introduction/apis.py` | 4 | `F401` (ruff) | `django.contrib.auth.authenticate` imported but unused |
| low | `introduction/apis.py` | 4 | `F401` (ruff) | `django.contrib.auth.login` imported but unused |
| low | `introduction/apis.py` | 6 | `F401` (ruff) | `django.shortcuts.redirect` imported but unused |
| low | `introduction/apis.py` | 10 | `F401` (ruff) | `introduction.playground.A9.main.Log` imported but unused |
| low | `introduction/apis.py` | 13 | `F403` (ruff) | `from .utility import *` used; unable to detect undefined names |
| low | `introduction/apis.py` | 14 | `F401` (ruff) | `.views.authentication_decorator` imported but unused |
| low | `introduction/apis.py` | 28 | `F405` (ruff) | `ssrf_code_converter` may be undefined, or defined from star imports |
| low | `introduction/apis.py` | 30 | `F405` (ruff) | `ssrf_html_input_extractor` may be undefined, or defined from star imports |
| low | `introduction/apis.py` | 66 | `F405` (ruff) | `os` may be undefined, or defined from star imports |
| low | `introduction/apis.py` | 67 | `F405` (ruff) | `os` may be undefined, or defined from star imports |
| low | `introduction/apis.py` | 68 | `F405` (ruff) | `os` may be undefined, or defined from star imports |
| low | `introduction/apis.py` | 122 | `F841` (ruff) | Local variable `e` is assigned to but never used |
| low | `introduction/apis.py` | 131 | `F405` (ruff) | `os` may be undefined, or defined from star imports |
| low | `introduction/apis.py` | 132 | `F405` (ruff) | `os` may be undefined, or defined from star imports |
| low | `introduction/lab_code/test.py` | 18 | `F401` (ruff) | `subprocess` imported but unused |
| low | `introduction/mitre.py` | 7 | `F401` (ruff) | `django.http.HttpResponse` imported but unused |
| low | `introduction/mitre.py` | 7 | `F401` (ruff) | `django.http.HttpResponseBadRequest` imported but unused |
| low | `introduction/playground/A9/archive.py` | 42 | `F811` (ruff) | Redefinition of unused `Log` from line 4: `Log` redefined here |
| low | `introduction/playground/A9/main.py` | 1 | `F401` (ruff) | `datetime` imported but unused |
| low | `introduction/tests.py` | 1 | `F401` (ruff) | `django.test.TestCase` imported but unused |
| low | `introduction/utility.py` | 5 | `F403` (ruff) | `from .models import *` used; unable to detect undefined names |
| low | `introduction/utility.py` | 53 | `F841` (ruff) | Local variable `id` is assigned to but never used |
| low | `introduction/views.py` | 4 | `F401` (ruff) | `json` imported but unused |
| low | `introduction/views.py` | 26 | `F401` (ruff) | `django.contrib.auth.authenticate` imported but unused |
| low | `introduction/views.py` | 27 | `F401` (ruff) | `django.contrib.auth.forms.UserCreationForm` imported but unused |
| low | `introduction/views.py` | 28 | `F401` (ruff) | `django.core.serializers` imported but unused |
| low | `introduction/views.py` | 29 | `F401` (ruff) | `django.http.JsonResponse` imported but unused |
| low | `introduction/views.py` | 31 | `F401` (ruff) | `django.template.loader` imported but unused |
| low | `introduction/views.py` | 35 | `F401` (ruff) | `requests.structures.CaseInsensitiveDict` imported but unused |
| low | `introduction/views.py` | 39 | `F401` (ruff) | `.models.info` imported but unused |
| low | `introduction/views.py` | 39 | `F811` (ruff) | Redefinition of unused `login` from line 26: `login` redefined here |
| low | `introduction/views.py` | 268 | `F841` (ruff) | Local variable `p` is assigned to but never used |
| low | `introduction/views.py` | 719 | `F601` (ruff) | Dictionary key literal `"error"` repeated |
| low | `introduction/views.py` | 1029 | `F841` (ruff) | Local variable `e` is assigned to but never used |

## Fixes aplicados (0)

Ninguno todavía.

## Ediciones generales auditadas (0)

Escrituras vía fs_write_file dentro de este proyecto (ya indexado por Codebase y con git) -- no vienen de un hallazgo puntual, pero pasan por el mismo circuito auditado y reversible.

Ninguna todavía.