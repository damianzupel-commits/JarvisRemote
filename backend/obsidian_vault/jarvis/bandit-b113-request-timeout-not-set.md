---
author: jarvis
category: seguridad
created: '2026-08-12T02:30:13.981896+00:00'
tags:
- investigacion
title: bandit B113 request timeout not set
updated: '2026-08-12T02:30:13.981896+00:00'
---

Investigación automática de Jarvis sobre "bandit B113 request timeout not set", basada en 4 página(s) reales visitadas.

## Fuentes

### B113: request_without_timeout — Bandit documentation
Fuente: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html

Bandit
 
[...enlaces de navegación del sitio omitidos...]
Continuous Integration and Deployment (CI/CD)
Frequently Asked Questions
 Test Plugins B113: request_without_timeout
View page source
B113: request_without_timeout
B113: Test for missing requests timeout

This plugin test checks for requests or httpx calls without a timeout specified.

Nearly all production code should use this parameter in nearly all requests, Failure to do so can cause your program to hang indefinitely.

When request methods are used without the timeout parameter set, Bandit will return a MEDIUM severity error.

Example
:

>> Issue: [B113:request_without_timeout] Call to requests without timeout
   Severity: Medium   Confidence: Low
   CWE: CWE-400 (https://cwe.mitre.org/data/definitions/400.html)
   More Info: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html
   Location: examples/requests-missing-timeout.py:3:0
2
3   requests.get('https://gmail.com')
4   requests.get('https://gmail.com', timeout=None)

--------------------------------------------------
>> Issue: [B113:request_without_timeout] Call to requests with timeout set to None
   Severity: Medium   Confidence: Low
   CWE: CWE-400 (https://cwe.mitre.org/data/definitions/400.html)
   More Info: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html
   Location: examples/requests-missing-timeout.py:4:0
3   requests.get('https://gmail.com')
4   requests.get('https://gmail.com', timeout=None)
5   requests.get('https://gmail.com', timeout=5)


See also

https://requests.readthedocs.io/en/latest/user/advanced/#timeouts

Added in version 1.7.5.

Changed in version 1.7.10: Added check for httpx module

 Previous
Next 

© Copyright 2026, Bandit Developers.

Built with Sphinx using a theme provided by Read the Docs.

### B113: request_without_timeout — Bandit documentation
Fuente: https://bandit.readthedocs.io/en/1.7.5/plugins/b113_request_without_timeout.html

[...enlaces de navegación del sitio omitidos...]

This plugin test checks for requests calls without a timeout specified.

Nearly all production code should use this parameter in nearly all requests, Failure to do so can cause your program to hang indefinitely.

When request methods are used without the timeout parameter set, Bandit will return a MEDIUM severity error.

Example:	
>> Issue: [B113:request_without_timeout] Requests call without timeout
   Severity: Medium   Confidence: Low
   CWE: CWE-400 (https://cwe.mitre.org/data/definitions/400.html)
   More Info: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html
   Location: examples/requests-missing-timeout.py:3:0
2
3   requests.get('https://gmail.com')
4   requests.get('https://gmail.com', timeout=None)

--------------------------------------------------
>> Issue: [B113:request_without_timeout] Requests call with timeout set to None
   Severity: Medium   Confidence: Low
   CWE: CWE-400 (https://cwe.mitre.org/data/definitions/400.html)
   More Info: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html
   Location: examples/requests-missing-timeout.py:4:0
3   requests.get('https://gmail.com')
4   requests.get('https://gmail.com', timeout=None)
5   requests.get('https://gmail.com', timeout=5)


See also

https://requests.readthedocs.io/en/latest/user/advanced/#timeouts

New in version 1.7.5.

Next 
 Previous

© Copyright 2022, Bandit Developers Revision ca4faf2f.

Built with Sphinx using a theme provided by Read the Docs.

### Bandit 1.7.5 false positive for request_without_timeout (B113) · Issue #996 · PyCQA/bandit · GitHub
Fuente: https://github.com/PyCQA/bandit/issues/996

[...enlaces de navegación del sitio omitidos...]
Bandit 1.7.5 false positive for request_without_timeout (B113)
[...enlaces de navegación del sitio omitidos...]

Bandit is incorrectly marking calls to requests library without a timeout while the code it's actually not calling directly the requests library and the timeout is already set elsewhere.

Reproduction steps
Define this code:
from mylibrary import my_session

class Repro:

    def __init__(self):
        self.requests = my_session(timeout=5)

    def get(self, uri):
        return self.requests.get(uri)

Run bandit: bandit -l -i -r --skip B404,B603 somepath/

Get an error:

>> Issue: [B113:request_without_timeout] Requests call without timeout
   Severity: Medium   Confidence: Low
   CWE: CWE-400 (https://cwe.mitre.org/data/definitions/400.html)
   More Info: https://bandit.readthedocs.io/en/1.7.5/plugins/b113_request_without_timeout.html
   Location: repro.py:10:15
9	    def get(self, uri):
10	        return self.requests.get(uri)
11

Expected behavior

Bandit should not report any error because the session has a default timeout set via an HTTPAdapter in another library.

The code calls self.requests that could be any kind of object, does bandit do code inspection of the object to detect that is actually a requests session?
I don't think so as it triggered the issue also with my pseudo code that doesn't import the real library.
If it was indeed doing introspection, it should probably also check if there is a default timeout set in the session.

Bandit version

1.7.5 (Default)

Python version

3.9,3.10

Additional context

[note] The dropdown menu of the issues template here on Github has a Python 3.1 version and is missing 3.10, possibly a typo in the template.

[...enlaces de navegación del sitio omitidos...]
© 2026 GitHub, Inc.
[...enlaces de navegación del sitio omitidos...]

### Fix Bandit B113 findings: Add missing request timeouts (16 occurrences) · Issue #518 · agentic-community/mcp-gateway-registry · GitHub
Fuente: https://github.com/agentic-community/mcp-gateway-registry/issues/518

[...enlaces de navegación del sitio omitidos...]
Fix Bandit B113 findings: Add missing request timeouts (16 occurrences)
[...enlaces de navegación del sitio omitidos...]

Addressing findings from the Bandit static security analysis tool. This issue targets B113 (request_without_timeout) -- 16 occurrences across the codebase where HTTP requests are made without explicit timeout parameters.

This is classified as an easy win since each fix is a one-line change: add timeout=30 (or an appropriate value) to the requests call.

Problem

HTTP requests without timeouts can hang indefinitely if the remote server is unresponsive, leading to resource exhaustion, thread starvation, or application hangs in production.

Bandit rule: B113 - request_without_timeout

Affected Files (16 occurrences)
agents/ (8 occurrences)
File	Line	Call
agents/a2a/test/agent_discovery_test.py	52	requests.post(endpoint, json=payload, headers=...)
agents/a2a/test/agent_simple_test.py	95	requests.post(endpoint, json=payload, headers=...)
agents/a2a/test/agent_simple_test.py	207	requests.get(url, params=params)
agents/a2a/test/agent_simple_test.py	209	requests.post(url, params=params)
agents/a2a/test/simple_agents_test.py	95	requests.post(endpoint, json=payload, headers=...)
agents/a2a/test/simple_agents_test.py	207	requests.get(url, params=params)
agents/a2a/test/simple_agents_test.py	209	requests.post(url, params=params)
agents/cli_user_auth.py	179	requests.post(TOKEN_URL, headers=headers, data=data)
agents/client.py (3 occurrences)
File	Line	Call
agents/client.py	209	requests.get(f"{args.server_url}/health")
agents/client.py	273	requests.post(f"{args.server_url}/validate", headers=headers)
agents/client.py	295	requests.get(f"{args.server_url}/config")
cli/ (2 occurrences)
File	Line	Call
cli/mcp_client.py	165	requests.post(token_url, data=data)
cli/test_asor_complete.py	48	requests.post(token_url, data=data)
credentials-provider/ (3 occurrences)
File	Line	Call
credentials-provider/agentcore-auth/generate_access_token.py	127	requests.post(url, headers=headers, json=data) (via lambda)
credentials-provider/agentcore-auth/generate_access_token.py	138	requests.post(url, headers=headers, data=data) (via lambda)
credentials-provider/keycloak/generate_tokens.py	103	requests.post(token_url, data=data, headers=headers)
Remediation

Add an explicit timeout parameter to each requests call. Recommended default: timeout=30 (30 seconds).

Example fix:

# Before
response = requests.post(token_url, data=data)

# After
response = requests.post(token_url, data=data, timeout=30)

For test files, a longer timeout may be appropriate (e.g., timeout=60) since tests may hit slower environments.

[...enlaces de navegación del sitio omitidos...]
© 2026 GitHub, Inc.
[...enlaces de navegación del sitio omitidos...]

## Notas relacionadas
- [[Reporte de auditoría -- httpie-cli -- 2026-07-29]]
- [[Reporte de auditoría -- pygoat -- 2026-07-29]]
- [[Gestion segura de contrasenas hashing bcrypt argon2 salting]]
- [[Reporte de auditoría -- django -- 2026-07-29]]
- [[Reporte de auditoría -- SuperSaaSFastAPI -- 2026-07-29]]
- [[Índice: seguridad]]