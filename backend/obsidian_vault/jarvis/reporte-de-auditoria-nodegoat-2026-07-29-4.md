---
author: jarvis
created: '2026-07-29T02:13:48.603593+00:00'
tags:
- reportes
- auditoria
- seguridad
- calidad
title: Reporte de auditoría -- NodeGoat -- 2026-07-29
updated: '2026-07-29T02:13:48.603593+00:00'
---

# Reporte de auditoría de código -- NodeGoat

- Proyecto: `C:\Users\dam\Documents\test-scans\NodeGoat`
- Generado: 2026-07-29T02:13:48.602553+00:00
- Último escaneo de seguridad: 2026-07-29T02:13:11.704026+00:00 (corrieron: semgrep, trivy)
- Último escaneo de calidad: 2026-07-29T02:13:12.586426+00:00 (corrieron: eslint)

## Resumen ejecutivo

119 hallazgo(s) de seguridad real(es) (11 crítico(s), 49 alto(s)). 397 hallazgo(s) de calidad (397 de severidad 'alta' según el propio analizador (Ruff/mypy/ESLint/tsc, el que haya corrido) -- no es un nivel de riesgo de seguridad).

## Hallazgos de seguridad (119)

| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |
|---|---|---|---|---|
| critical | `package-lock.json` | 1 | `CVE-2020-7610` (trivy) | bson 1.0.9: bson: Deserialization of Untrusted Data could result in Code injection or Excessive CPU load (fix: 1.1.4) |
| critical | `package-lock.json` | 1 | `CVE-2023-45311` (trivy) | fsevents 1.2.9: Code injection in fsevents (fix: 1.2.11) |
| critical | `package-lock.json` | 1 | `CVE-2021-44906` (trivy) | minimist 0.0.10: minimist: prototype pollution (fix: 1.2.6, 0.2.4) |
| critical | `package-lock.json` | 1 | `CVE-2021-44906` (trivy) | minimist 0.0.8: minimist: prototype pollution (fix: 1.2.6, 0.2.4) |
| critical | `package-lock.json` | 1 | `CVE-2021-44906` (trivy) | minimist 1.2.0: minimist: prototype pollution (fix: 1.2.6, 0.2.4) |
| critical | `package-lock.json` | 1 | `CVE-2021-44906` (trivy) | minimist 1.2.5: minimist: prototype pollution (fix: 1.2.6, 0.2.4) |
| critical | `package-lock.json` | 1 | `CVE-2019-10746` (trivy) | mixin-deep 1.3.1: nodejs-mixin-deep: prototype pollution in function mixin-deep (fix: 1.3.2, 2.0.1) |
| critical | `package-lock.json` | 1 | `CVE-2019-10747` (trivy) | set-value 0.4.3: nodejs-set-value: prototype pollution in function set-value (fix: 2.0.1, 3.0.1) |
| critical | `package-lock.json` | 1 | `CVE-2019-10747` (trivy) | set-value 2.0.0: nodejs-set-value: prototype pollution in function set-value (fix: 2.0.1, 3.0.1) |
| critical | `package-lock.json` | 1 | `CVE-2026-59873` (trivy) | tar 4.4.8: tar: node-tar: Denial of Service via crafted gzip bomb (fix: 7.5.19) |
| critical | `package-lock.json` | 1 | `CVE-2021-23358` (trivy) | underscore 1.9.1: nodejs-underscore: Arbitrary code execution via the template function (fix: 1.12.1) |
| high | `app/routes/contributions.js` | 32 | `javascript.lang.security.audit.code-string-concat.code-string-concat` (semgrep) | Found data from an Express or Next web request flowing to `eval`. If this data is user-controllable this can lead to execution of arbitrary system commands in t |
| high | `app/routes/contributions.js` | 33 | `javascript.lang.security.audit.code-string-concat.code-string-concat` (semgrep) | Found data from an Express or Next web request flowing to `eval`. If this data is user-controllable this can lead to execution of arbitrary system commands in t |
| high | `app/routes/contributions.js` | 34 | `javascript.lang.security.audit.code-string-concat.code-string-concat` (semgrep) | Found data from an Express or Next web request flowing to `eval`. If this data is user-controllable this can lead to execution of arbitrary system commands in t |
| high | `artifacts/cert/server.key` | 1 | `generic.secrets.security.detected-private-key.detected-private-key` (semgrep) | Private Key detected. This is a sensitive credential and should not be hardcoded here. Instead, store this in a separate, private file. |
| high | `artifacts/db-reset.js` | 19 | `generic.secrets.security.detected-bcrypt-hash.detected-bcrypt-hash` (semgrep) | bcrypt hash detected |
| high | `artifacts/db-reset.js` | 28 | `generic.secrets.security.detected-bcrypt-hash.detected-bcrypt-hash` (semgrep) | bcrypt hash detected |
| high | `artifacts/db-reset.js` | 36 | `generic.secrets.security.detected-bcrypt-hash.detected-bcrypt-hash` (semgrep) | bcrypt hash detected |
| high | `package-lock.json` | 1 | `CVE-2024-45590` (trivy) | body-parser 1.18.3: body-parser: Denial of Service Vulnerability in body-parser (fix: 1.20.3) |
| high | `package-lock.json` | 1 | `CVE-2026-13149` (trivy) | brace-expansion 1.1.11: brace-expansion: Brace-expansion: Denial of Service due to exponential-time complexity (fix: 5.0.7, 1.1.16, 2.1.2) |
| high | `package-lock.json` | 1 | `CVE-2026-14257` (trivy) | brace-expansion 1.1.11: brace-expansion through 5.0.7 is vulnerable to denial of service via m ... (fix: 5.0.8) |
| high | `package-lock.json` | 1 | `CVE-2024-4068` (trivy) | braces 2.3.2: braces: fails to limit the number of characters it can handle (fix: 3.0.3) |
| high | `package-lock.json` | 1 | `CVE-2017-20165` (trivy) | debug 2.2.0: A vulnerability classified as problematic has been found in debug-js d ... (fix: 3.1.0, 2.6.9) |
| high | `package-lock.json` | 1 | `CVE-2022-38900` (trivy) | decode-uri-component 0.2.0: decode-uri-component: improper input validation resulting in DoS (fix: 0.2.1) |
| high | `package-lock.json` | 1 | `CVE-2021-3820` (trivy) | i 0.3.6: inflect vulnerable to Inefficient Regular Expression Complexity (fix: 0.3.7) |
| high | `package-lock.json` | 1 | `CVE-2020-7788` (trivy) | ini 1.3.5: nodejs-ini: Prototype pollution via malicious INI file (fix: 1.3.6) |
| high | `package-lock.json` | 1 | `CVE-2019-20149` (trivy) | kind-of 6.0.2: nodejs-kind-of: ctorName in index.js allows external user input to overwrite certain internal attributes (fix: 6.0.3) |
| high | `package-lock.json` | 1 | `CVE-2017-16114` (trivy) | marked 0.3.5: The marked module is vulnerable to a regular expression denial of serv ... (fix: 0.3.9) |
| high | `package-lock.json` | 1 | `CVE-2022-21680` (trivy) | marked 0.3.5: marked: regular expression block.def may lead Denial of Service (fix: 4.0.10) |
| high | `package-lock.json` | 1 | `CVE-2022-21681` (trivy) | marked 0.3.5: marked: regular expression inline.reflinkSearch may lead Denial of Service (fix: 4.0.10) |
| high | `package-lock.json` | 1 | `CVE-2022-3517` (trivy) | minimatch 3.0.4: nodejs-minimatch: ReDoS via the braceExpand function (fix: 3.0.5) |
| high | `package-lock.json` | 1 | `CVE-2026-26996` (trivy) | minimatch 3.0.4: minimatch: minimatch: Denial of Service via specially crafted glob patterns (fix: 10.2.1, 9.0.6, 8.0.5, 7.4.7, 6.2.1, 5.1.7, 4.2.4, 3.1.3) |
| high | `package-lock.json` | 1 | `CVE-2026-27903` (trivy) | minimatch 3.0.4: minimatch: minimatch: Denial of Service due to unbounded recursive backtracking via crafted glob patterns (fix: 10.2.3, 9.0.7, 8.0.6, 7.4.8, 6. |
| high | `package-lock.json` | 1 | `CVE-2026-27904` (trivy) | minimatch 3.0.4: minimatch: Minimatch: Denial of Service via catastrophic backtracking in glob expressions (fix: 10.2.3, 9.0.7, 8.0.6, 7.4.8, 6.2.2, 5.1.8, 4.2. |
| high | `package-lock.json` | 1 | `GHSA-mh5c-679w-hh4r` (trivy) | mongodb 2.2.36: Denial of Service in mongodb (fix: 3.1.13) |
| high | `package-lock.json` | 1 | `CVE-2022-21803` (trivy) | nconf 0.10.0: nconf: Prototype pollution in memory store (fix: 0.11.4) |
| high | `package-lock.json` | 1 | `CVE-2022-21803` (trivy) | nconf 0.6.9: nconf: Prototype pollution in memory store (fix: 0.11.4) |
| high | `package-lock.json` | 1 | `CVE-2024-45296` (trivy) | path-to-regexp 0.1.7: path-to-regexp: Backtracking regular expressions cause ReDoS (fix: 1.9.0, 0.1.10, 8.0.0, 3.3.0, 6.3.0) |
| high | `package-lock.json` | 1 | `CVE-2024-52798` (trivy) | path-to-regexp 0.1.7: path-to-regexp: path-to-regexp Unpatched `path-to-regexp` ReDoS in 0.1.x (fix: 0.1.12) |
| high | `package-lock.json` | 1 | `CVE-2026-4867` (trivy) | path-to-regexp 0.1.7: path-to-regexp: path-to-regexp: Denial of Service via catastrophic backtracking from malformed URL parameters (fix: 0.1.13) |
| high | `package-lock.json` | 1 | `CVE-2022-24999` (trivy) | qs 6.5.2: express: "qs" prototype poisoning causes the hang of the node process (fix: 6.10.3, 6.9.7, 6.8.3, 6.7.3, 6.6.1, 6.5.3, 6.4.1, 6.3.3, 6.2.4) |
| high | `package-lock.json` | 1 | `CVE-2022-25883` (trivy) | semver 5.6.0: nodejs-semver: Regular expression denial of service (fix: 7.5.2, 6.3.1, 5.7.2) |
| high | `package-lock.json` | 1 | `CVE-2022-25883` (trivy) | semver 5.7.0: nodejs-semver: Regular expression denial of service (fix: 7.5.2, 6.3.1, 5.7.2) |
| high | `package-lock.json` | 1 | `CVE-2021-23440` (trivy) | set-value 0.4.3: nodejs-set-value: type confusion allows bypass of CVE-2019-10747 (fix: 4.0.1, 2.0.1, 3.0.3) |
| high | `package-lock.json` | 1 | `CVE-2021-23440` (trivy) | set-value 2.0.0: nodejs-set-value: type confusion allows bypass of CVE-2019-10747 (fix: 4.0.1, 2.0.1, 3.0.3) |
| high | `package-lock.json` | 1 | `CVE-2023-25345` (trivy) | swig 1.4.2: Arbitrary local file read vulnerability during template rendering  (fix: sin fix disponible) |
| high | `package-lock.json` | 1 | `CVE-2021-32803` (trivy) | tar 4.4.8: nodejs-tar: Insufficient symlink protection allowing arbitrary file creation and overwrite (fix: 3.2.3, 4.4.15, 5.0.7, 6.1.2) |
| high | `package-lock.json` | 1 | `CVE-2021-32804` (trivy) | tar 4.4.8: nodejs-tar: Insufficient absolute path sanitization allowing arbitrary file creation and overwrite (fix: 3.2.2, 4.4.14, 5.0.6, 6.1.1) |
| high | `package-lock.json` | 1 | `CVE-2021-37701` (trivy) | tar 4.4.8: nodejs-tar: Insufficient symlink protection due to directory cache poisoning using symbolic links allowing arbitrary file creation and overwrite (fix |
| high | `package-lock.json` | 1 | `CVE-2021-37712` (trivy) | tar 4.4.8: nodejs-tar: Insufficient symlink protection due to directory cache poisoning using symbolic links allowing arbitrary file creation and overwrite (fix |
| high | `package-lock.json` | 1 | `CVE-2021-37713` (trivy) | tar 4.4.8: nodejs-tar: Arbitrary File Creation/Overwrite on Windows via insufficient relative path sanitization (fix: 4.4.18, 5.0.10, 6.1.9) |
| high | `package-lock.json` | 1 | `CVE-2026-23745` (trivy) | tar 4.4.8: node-tar: tar: node-tar: Arbitrary file overwrite and symlink poisoning via unsanitized linkpaths in archives (fix: 7.5.3) |
| high | `package-lock.json` | 1 | `CVE-2026-23950` (trivy) | tar 4.4.8: node-tar: tar: node-tar: Arbitrary file overwrite via Unicode path collision race condition (fix: 7.5.4) |
| high | `package-lock.json` | 1 | `CVE-2026-24842` (trivy) | tar 4.4.8: node-tar: tar: node-tar: Arbitrary file creation via path traversal bypass in hardlink security check (fix: 7.5.7) |
| high | `package-lock.json` | 1 | `CVE-2026-26960` (trivy) | tar 4.4.8: node-tar: node-tar: Arbitrary file read/write via malicious archive hardlink creation (fix: 7.5.8) |
| high | `package-lock.json` | 1 | `CVE-2026-29786` (trivy) | tar 4.4.8: node-tar: hardlink path traversal via drive-relative linkpath (fix: 7.5.10) |
| high | `package-lock.json` | 1 | `CVE-2026-31802` (trivy) | tar 4.4.8: tar: tar: File overwrite via drive-relative symlink traversal (fix: 7.5.11) |
| high | `package-lock.json` | 1 | `CVE-2026-59874` (trivy) | tar 4.4.8: tar: Node-tar: Denial of Service via malformed tar archive header (fix: 7.5.18) |
| high | `package-lock.json` | 1 | `CVE-2026-27601` (trivy) | underscore 1.9.1: Underscore.js: Underscore.js: Denial of Service via recursive data structures in flatten and isEqual functions (fix: 1.13.8) |
| high | `package-lock.json` | 1 | `CVE-2020-7774` (trivy) | y18n 3.2.1: nodejs-y18n: prototype pollution vulnerability (fix: 3.2.2, 4.0.1, 5.0.5) |
| medium | `.github/workflows/e2e-test.yml` | 16 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `.github/workflows/e2e-test.yml` | 21 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `.github/workflows/e2e-test.yml` | 26 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `.github/workflows/e2e-test.yml` | 58 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `.github/workflows/lint.yml` | 16 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `.github/workflows/lint.yml` | 21 | `yaml.github-actions.security.github-actions-mutable-action-tag.github-actions-mutable-action-tag` (semgrep) | GitHub Actions step uses a mutable tag or branch reference. Tags and branch names can be silently repointed by the action owner, enabling supply-chain attacks â |
| medium | `app/routes/contributions.js` | 32 | `javascript.browser.security.eval-detected.eval-detected` (semgrep) | Detected the use of eval(). eval() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a co |
| medium | `app/routes/contributions.js` | 33 | `javascript.browser.security.eval-detected.eval-detected` (semgrep) | Detected the use of eval(). eval() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a co |
| medium | `app/routes/contributions.js` | 34 | `javascript.browser.security.eval-detected.eval-detected` (semgrep) | Detected the use of eval(). eval() can be dangerous if used to evaluate dynamic content. If this content can be input from outside the program, this may be a co |
| medium | `app/routes/index.js` | 72 | `javascript.express.security.audit.express-open-redirect.express-open-redirect` (semgrep) | The application redirects to a URL specified by user-supplied input `req` that is not validated. This could redirect users to malicious locations. Consider usin |
| medium | `app/views/benefits.html` | 54 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `app/views/login.html` | 107 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `app/views/memos.html` | 15 | `python.django.security.django-no-csrf-token.django-no-csrf-token` (semgrep) | Manually-created forms in django templates should specify a csrf_token to prevent CSRF attacks. |
| medium | `app/views/tutorial/a2.html` | 207 | `html.security.plaintext-http-link.plaintext-http-link` (semgrep) | This link points to a plaintext HTTP URL. Prefer an encrypted HTTPS URL if possible. |
| medium | `app/views/tutorial/a2.html` | 209 | `html.security.plaintext-http-link.plaintext-http-link` (semgrep) | This link points to a plaintext HTTP URL. Prefer an encrypted HTTPS URL if possible. |
| medium | `app/views/tutorial/a2.html` | 210 | `html.security.plaintext-http-link.plaintext-http-link` (semgrep) | This link points to a plaintext HTTP URL. Prefer an encrypted HTTPS URL if possible. |
| medium | `app/views/tutorial/a5.html` | 50 | `html.security.plaintext-http-link.plaintext-http-link` (semgrep) | This link points to a plaintext HTTP URL. Prefer an encrypted HTTPS URL if possible. |
| medium | `app/views/tutorial/a5.html` | 51 | `html.security.plaintext-http-link.plaintext-http-link` (semgrep) | This link points to a plaintext HTTP URL. Prefer an encrypted HTTPS URL if possible. |
| medium | `docker-compose.yml` | 13 | `yaml.docker-compose.security.no-new-privileges.no-new-privileges` (semgrep) | Service 'mongo' allows for privilege escalation via setuid or setgid binaries. Add 'no-new-privileges:true' in 'security_opt' to prevent this. |
| medium | `docker-compose.yml` | 13 | `yaml.docker-compose.security.writable-filesystem-service.writable-filesystem-service` (semgrep) | Service 'mongo' is running with a writable root filesystem. This may allow malicious applications to download and run additional payloads, or modify container f |
| medium | `package-lock.json` | 1 | `CVE-2026-33750` (trivy) | brace-expansion 1.1.11: brace-expansion: brace-expansion: Denial of Service via zero step value in brace pattern (fix: 5.0.5, 3.0.2, 2.0.3, 1.1.13) |
| medium | `package-lock.json` | 1 | `CVE-2019-2391` (trivy) | bson 1.0.9: Incorrect parsing of certain JSON input may result in js-bson not corr ... (fix: 1.1.4) |
| medium | `package-lock.json` | 1 | `CVE-2024-29041` (trivy) | express 4.16.4: express: cause malformed URLs to be evaluated (fix: 4.19.2, 5.0.0-beta.3) |
| medium | `package-lock.json` | 1 | `GHSA-c3m8-x3cg-qm2c` (trivy) | helmet-csp 1.2.2: Configuration Override in helmet-csp (fix: 2.9.1) |
| medium | `package-lock.json` | 1 | `CVE-2016-10531` (trivy) | marked 0.3.5: marked is an application that is meant to parse and compile markdown.  ... (fix: 0.3.6) |
| medium | `package-lock.json` | 1 | `CVE-2017-1000427` (trivy) | marked 0.3.5: marked version 0.3.6 and earlier is vulnerable to an XSS attack in the ... (fix: 0.3.7) |
| medium | `package-lock.json` | 1 | `CVE-2018-25110` (trivy) | marked 0.3.5: Marked prior to version 0.3.17 is vulnerable to a Regular Expression D ... (fix: 0.3.17) |
| medium | `package-lock.json` | 1 | `NSWG-ECO-101` (trivy) | marked 0.3.5: Sanitization bypass using HTML Entities (fix: >=0.3.6) |
| medium | `package-lock.json` | 1 | `CVE-2024-4067` (trivy) | micromatch 3.1.10: micromatch: vulnerable to Regular Expression Denial of Service (fix: 4.0.8) |
| medium | `package-lock.json` | 1 | `CVE-2020-7598` (trivy) | minimist 0.0.10: nodejs-minimist: prototype pollution allows adding or modifying properties of Object.prototype using a constructor or __proto__ payload (fix: 0 |
| medium | `package-lock.json` | 1 | `CVE-2020-7598` (trivy) | minimist 0.0.8: nodejs-minimist: prototype pollution allows adding or modifying properties of Object.prototype using a constructor or __proto__ payload (fix: 0. |
| medium | `package-lock.json` | 1 | `CVE-2020-7598` (trivy) | minimist 1.2.0: nodejs-minimist: prototype pollution allows adding or modifying properties of Object.prototype using a constructor or __proto__ payload (fix: 0. |
| medium | `package-lock.json` | 1 | `CVE-2017-20162` (trivy) | ms 0.7.1: Vercel ms Inefficient Regular Expression Complexity vulnerability (fix: 2.0.0) |
| medium | `package-lock.json` | 1 | `CVE-2025-15284` (trivy) | qs 6.5.2: qs: qs: Denial of Service via improper input validation in array parsing (fix: 6.14.1) |
| medium | `package-lock.json` | 1 | `CVE-2024-28863` (trivy) | tar 4.4.8: node-tar: denial of service while parsing a tar file due to lack of folders depth validation (fix: 6.2.1) |
| medium | `package-lock.json` | 1 | `CVE-2026-53655` (trivy) | tar 4.4.8: node-tar: node-tar: File smuggling due to inconsistent tar archive parsing (fix: 7.5.16) |
| medium | `package-lock.json` | 1 | `CVE-2026-59871` (trivy) | tar 4.4.8: node-tar: node-tar: Denial of Service due to incorrect PAX path handling (fix: 7.5.18) |
| medium | `package-lock.json` | 1 | `CVE-2026-59875` (trivy) | tar 4.4.8: node-tar: node-tar: Denial of Service via crafted archive with NUL bytes in metadata (fix: 7.5.17) |
| medium | `package-lock.json` | 1 | `GHSA-r292-9mhp-454m` (trivy) | tar 4.4.8: node-tar: Uncontrolled recursion in mapHas/filesFilter allows uncatchable stack-overflow DoS via crafted long-path tar with member selection (fix: 7. |
| medium | `package-lock.json` | 1 | `CVE-2015-8858` (trivy) | uglify-js 2.4.24: The uglify-js package before 2.6.0 for Node.js allows attackers to cau ... (fix: >=2.6.0) |
| medium | `server.js` | 78 | `javascript.express.security.audit.express-cookie-settings.express-cookie-session-default-name` (semgrep) | Donâ€™t use the default session cookie name Using the default session cookie name can open your app to attacks. The security issue posed is similar to X-Powered |
| medium | `server.js` | 78 | `javascript.express.security.audit.express-cookie-settings.express-cookie-session-no-domain` (semgrep) | Default session middleware settings: `domain` not set. It indicates the domain of the cookie; use it to compare against the domain of the server in which the UR |
| medium | `server.js` | 78 | `javascript.express.security.audit.express-cookie-settings.express-cookie-session-no-expires` (semgrep) | Default session middleware settings: `expires` not set. Use it to set expiration date for persistent cookies. |
| medium | `server.js` | 78 | `javascript.express.security.audit.express-cookie-settings.express-cookie-session-no-httponly` (semgrep) | Default session middleware settings: `httpOnly` not set. It ensures the cookie is sent only over HTTP(S), not client JavaScript, helping to protect against cros |
| medium | `server.js` | 78 | `javascript.express.security.audit.express-cookie-settings.express-cookie-session-no-path` (semgrep) | Default session middleware settings: `path` not set. It indicates the path of the cookie; use it to compare against the request path. If this and domain match,  |
| medium | `server.js` | 78 | `javascript.express.security.audit.express-cookie-settings.express-cookie-session-no-secure` (semgrep) | Default session middleware settings: `secure` not set. It ensures the browser only sends the cookie over HTTPS. |
| medium | `server.js` | 145 | `problem-based-packs.insecure-transport.js-node.using-http-server.using-http-server` (semgrep) | Checks for any usage of http servers instead of https servers. Encourages the usage of https protocol instead of http, which does not have TLS and is therefore  |
| low | `package-lock.json` | 1 | `CVE-2026-12590` (trivy) | body-parser 1.18.3: body-parser: body-parser: Denial of Service via invalid limit option (fix: 1.20.6, 2.3.0) |
| low | `package-lock.json` | 1 | `CVE-2025-5889` (trivy) | brace-expansion 1.1.11: brace-expansion: juliangruber brace-expansion index.js expand redos (fix: 2.0.2, 1.1.12, 3.0.1, 4.0.1) |
| low | `package-lock.json` | 1 | `CVE-2024-47764` (trivy) | cookie 0.3.1: cookie: cookie accepts cookie name, path, and domain with out of bounds characters (fix: 0.7.0) |
| low | `package-lock.json` | 1 | `CVE-2017-16137` (trivy) | debug 2.2.0: nodejs-debug: Regular expression Denial of Service (fix: 2.6.9, 3.1.0, 3.2.7, 4.3.1) |
| low | `package-lock.json` | 1 | `CVE-2017-16137` (trivy) | debug 4.1.1: nodejs-debug: Regular expression Denial of Service (fix: 2.6.9, 3.1.0, 3.2.7, 4.3.1) |
| low | `package-lock.json` | 1 | `CVE-2024-43796` (trivy) | express 4.16.4: express: Improper Input Handling in Express Redirects (fix: 4.20.0, 5.0.0) |
| low | `package-lock.json` | 1 | `CVE-2025-7339` (trivy) | on-headers 1.0.1: on-headers: on-headers vulnerable to http response header manipulation (fix: 1.1.0) |
| low | `package-lock.json` | 1 | `CVE-2024-43799` (trivy) | send 0.16.2: send: Code Execution Vulnerability in Send Library (fix: 0.19.0) |
| low | `package-lock.json` | 1 | `CVE-2024-43800` (trivy) | serve-static 1.13.2: serve-static: Improper Sanitization in serve-static (fix: 1.16.0, 2.1.0) |
| low | `package-lock.json` | 1 | `NSWG-ECO-445` (trivy) | utile 0.2.1: Out-of-bounds Read (fix: sin fix disponible) |
| low | `package-lock.json` | 1 | `NSWG-ECO-445` (trivy) | utile 0.3.0: Out-of-bounds Read (fix: sin fix disponible) |
| low | `server.js` | 15 | `javascript.express.security.audit.express-check-csurf-middleware-usage.express-check-csurf-middleware-usage` (semgrep) | A CSRF middleware was not detected in your express application. Ensure you are either using one such as `csurf` or `csrf` (see rule references) and/or you are p |

## Hallazgos de calidad (397)

| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |
|---|---|---|---|---|
| high | `app/data/contributions-dao.js` | 86 | `no-irregular-whitespace` (eslint) | Irregular whitespace not allowed. |
| high | `app/data/memos-dao.js` | 39 | `no-irregular-whitespace` (eslint) | Irregular whitespace not allowed. |
| high | `app/data/research-dao.js` | 13 | `no-unused-vars` (eslint) | 'callback' is defined but never used. |
| high | `app/data/research-dao.js` | 15 | `no-unused-vars` (eslint) | 'searchCriteria' is assigned a value but never used. |
| high | `app/data/user-dao.js` | 1 | `no-unused-vars` (eslint) | 'bcrypt' is assigned a value but never used. |
| high | `app/data/user-dao.js` | 123 | `no-irregular-whitespace` (eslint) | Irregular whitespace not allowed. |
| high | `app/routes/error.js` | 3 | `no-unused-vars` (eslint) | 'next' is defined but never used. |
| high | `app/routes/index.js` | 27 | `no-unused-vars` (eslint) | 'isAdmin' is assigned a value but never used. |
| high | `app/routes/memos.js` | 13 | `no-unused-vars` (eslint) | 'docs' is defined but never used. |
| high | `app/routes/profile.js` | 59 | `no-useless-escape` (eslint) | Unnecessary escape character: \#. |
| high | `app/routes/research.js` | 10 | `no-unused-vars` (eslint) | 'researchDAO' is assigned a value but never used. |
| high | `app/routes/session.js` | 44 | `no-unused-vars` (eslint) | 'next' is defined but never used. |
| high | `app/routes/session.js` | 59 | `no-unused-vars` (eslint) | 'errorMessage' is assigned a value but never used. |
| high | `artifacts/db-reset.js` | 40 | `no-unused-vars` (eslint) | 'reject' is defined but never used. |
| high | `artifacts/db-reset.js` | 41 | `no-unused-vars` (eslint) | 'data' is defined but never used. |
| high | `config/config.js` | 1 | `no-unused-vars` (eslint) | '_' is assigned a value but never used. |
| high | `test/e2e/integration/allocations_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 6 | `no-undef` (eslint) | 'before' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 10 | `no-undef` (eslint) | 'afterEach' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 11 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 14 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 15 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 16 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 19 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 20 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 21 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 22 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 25 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 26 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 27 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 28 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 31 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 33 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 34 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 36 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 40 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 43 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 44 | `no-undef` (eslint) | 'expect' is not defined. |
| high | `test/e2e/integration/allocations_spec.js` | 45 | `no-undef` (eslint) | 'expect' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 6 | `no-undef` (eslint) | 'before' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 10 | `no-undef` (eslint) | 'afterEach' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 11 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 14 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 15 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 16 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 19 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 20 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 21 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 22 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 25 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 26 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 27 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 28 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 31 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 32 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 33 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 34 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 37 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 38 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 39 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 40 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 44 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 48 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/benefits_spec.js` | 49 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 6 | `no-undef` (eslint) | 'before' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 10 | `no-undef` (eslint) | 'afterEach' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 11 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 14 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 15 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 16 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 19 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 20 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 21 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 22 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 25 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 26 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 27 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 28 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 33 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 35 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 36 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 37 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 43 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 46 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 50 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/contributions_spec.js` | 53 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 6 | `no-undef` (eslint) | 'afterEach' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 10 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 11 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 12 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 15 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 16 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 17 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 18 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 21 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 22 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 23 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 24 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 25 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 30 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 31 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 32 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 33 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/dashboard_spec.js` | 34 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 6 | `no-undef` (eslint) | 'beforeEach' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 8 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 11 | `no-undef` (eslint) | 'afterEach' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 12 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 15 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 16 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 20 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 24 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 28 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 32 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 38 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 43 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 47 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 52 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 53 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 58 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 64 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 71 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 72 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/general_spec.js` | 73 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 6 | `no-undef` (eslint) | 'afterEach' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 10 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 11 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 12 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 15 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 16 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 17 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/learn_spec.js` | 18 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 6 | `no-undef` (eslint) | 'before' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 10 | `no-undef` (eslint) | 'afterEach' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 11 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 14 | `no-undef` (eslint) | 'beforeEach' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 15 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 18 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 19 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 24 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 25 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 28 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 29 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 33 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 34 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 35 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 36 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 37 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 38 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 39 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 43 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 44 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 45 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 46 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 47 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 48 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 49 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 53 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 54 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 55 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 56 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 57 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 58 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 60 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 62 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 68 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 69 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 70 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 71 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 72 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 73 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 75 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 77 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 83 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 84 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 88 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 89 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/login_spec.js` | 90 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 3 | `no-undef` (eslint) | 'describe' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 6 | `no-undef` (eslint) | 'before' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 7 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 10 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 11 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 12 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 15 | `no-undef` (eslint) | 'it' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 16 | `no-undef` (eslint) | 'cy' is not defined. |
| high | `test/e2e/integration/logout_spec.js` | 17 | `no-undef` (eslint) | 'cy' is not defined. |

_(+197 más, omitidos por espacio)_

## Fixes aplicados (0)

Ninguno todavía.

## Ediciones generales auditadas (0)

Escrituras vía fs_write_file dentro de este proyecto (ya indexado por Codebase y con git) -- no vienen de un hallazgo puntual, pero pasan por el mismo circuito auditado y reversible.

Ninguna todavía.