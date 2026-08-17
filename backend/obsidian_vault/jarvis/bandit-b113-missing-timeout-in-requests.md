---
author: jarvis
category: seguridad
created: '2026-08-12T02:48:34.661019+00:00'
tags:
- investigacion
title: Bandit B113 missing timeout in requests
updated: '2026-08-12T02:48:34.661019+00:00'
---

Investigación automática de Jarvis sobre "Bandit B113 missing timeout in requests", basada en 4 página(s) reales visitadas.

## Fuentes

### B113: request_without_timeout — Bandit documentation
Fuente: https://bandit.readthedocs.io/en/latest/plugins/b113_request_without_timeout.html

[...enlaces de navegación del sitio omitidos...]
 
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

### Python Security - Fix B113 (Missing Request Timeouts) · Issue #598 · agentic-community/mcp-gateway-registry · GitHub
Fuente: https://github.com/agentic-community/mcp-gateway-registry/issues/598

[...enlaces de navegación del sitio omitidos...]
Python Security - Fix B113 (Missing Request Timeouts)
[...enlaces de navegación del sitio omitidos...]
Python Security - Fix B113 (Missing Request Timeouts)

Parent Issue: #597
Category: Python Code Security
Priority: Medium

Overview

Fix 16 instances of missing timeout parameters on HTTP requests across 8 files. All HTTP requests should include timeout parameters to prevent indefinite hangs and potential DoS vulnerabilities.

Summary
Files Affected: 8 files
Total Instances: 16 findings
Severity: HIGH (Bandit B113)
Estimated Time: 1-2 hours
Status Breakdown
✅ Likely Already Fixed: 3 files (verification only)
🔴 Need Fixes: 3-4 production files
⚠️ Test Files: 3 files (exclude from future scans)
Files Requiring Fixes
Priority 1: Production Code (MUST FIX)

agents/cli_user_auth.py (Line 178)

Add timeout=30 to requests.post()

credentials-provider/agentcore-auth/generate_access_token.py (Lines 126, 137)

Add timeout=30 to both requests.post() calls

credentials-provider/keycloak/generate_tokens.py (Line 102)

Add timeout=30 to requests.post()
Priority 2: Verify Status

agents/client.py (Lines 208, 272, 294)

Previous analysis suggests these already have timeout=30
Verify and mark as false positive if correct

cli/test_asor_complete.py (Line 47)

Verify and fix if needed

cli/mcp_client.py (Line 164)

Verify and fix if needed
Priority 3: Test Files (Low Priority)

7-9. Agent test files (7 total instances)

agents/a2a/test/agent_discovery_test.py
agents/a2a/test/agent_simple_test.py
agents/a2a/test/simple_agents_test.py
Recommended: Exclude test files from Bandit scans
Implementation Plan
Phase 1: Verification (15-30 min)
 Run fresh Bandit scan to identify current status
 Verify agents/client.py already has timeouts
 Check Priority 1 files for missing timeouts
Phase 2: Fix Production Code (30-45 min)
 Fix agents/cli_user_auth.py
 Fix credentials-provider/agentcore-auth/generate_access_token.py (2 locations)
 Fix credentials-provider/keycloak/generate_tokens.py
 Verify and fix CLI files if needed
Phase 3: Configuration (15 min)
 Update .bandit or pyproject.toml to exclude test files
 Run Bandit to verify test files excluded
Phase 4: Validation (15 min)
 Run full Bandit scan and verify B113 count reduced
 Run tests to ensure no regressions
 Update security baseline
Standard Fix Pattern
# Before
response = requests.post(url, json=payload, headers=headers)

# After
response = requests.post(url, json=payload, headers=headers, timeout=30)
Verification Commands
# Count B113 findings before
uv run bandit -r . -f json | grep -c '"test_id": "B113"'

# After excluding test files
uv run bandit -r . -f json --exclude "*/test/*,*_test.py" | grep -c '"test_id": "B113"'
Expected Outcome
Before: 16 B113 findings
After: 0-3 findings (verified false positives only)
All production code with proper timeout parameters
Test files excluded from future scans
Acceptance Criteria
 All production code HTTP requests have timeout pa

## Notas relacionadas
- [[bandit B113 request timeout not set]]
- [[Reporte de auditoría -- SuperSaaSFastAPI -- 2026-07-29]]
- [[Reporte de auditoría -- httpie-cli -- 2026-07-29]]
- [[Reporte de auditoría -- pygoat -- 2026-07-29]]
- [[Reporte de auditoría -- saas-boilerplate -- 2026-07-29]]
- [[Índice: seguridad]]