---
author: jarvis
category: pentesting
created: '2026-08-02T19:59:27.335444+00:00'
tags:
- investigacion
title: API security OWASP API Top 10
updated: '2026-08-02T19:59:27.335444+00:00'
---

Investigación automática de Jarvis sobre "API security OWASP API Top 10", basada en 4 página(s) reales visitadas.

## Fuentes

### OWASP API Security Top 10 - OWASP API Security Top 10
Fuente: https://owasp.org/API-Security/

Skip to content
OWASP API Security Top 10
OWASP API Security Top 10
Initializing search
 OWASP/API-Security
Home
 
2023
 
2019
Home
How-to Contribute
Table of contents
Description
Project Leaders
Licensing
OWASP API Security Top 10

This project is designed to address the ever-increasing number of organizations that are deploying potentially sensitive APIs as part of their software offerings. These APIs are used for internal tasks and to interface with third parties. Unfortunately, many APIs do not undergo the rigorous security testing that would help make them secure from an attack.

The OWASP API Security Project seeks to provide value to software developers and security assessors by underscoring the potential risks in insecure APIs, and illustrating how these risks may be mitigated. In order to facilitate this goal, the OWASP API Security Project will create and maintain a Top 10 API Security Risks document, as well as a documentation portal for best practices when creating or assessing APIs.

Description

While working as developers or information security consultants, many people have encountered APIs as part of a project. While there are some resources to help create and evaluate these projects (such as the OWASP REST Security Cheat Sheet), there has not be a comprehensive security project designed to assist builders, breakers, and defenders in the community.

This project aims to:

Create the OWASP Top Ten API Security Risks document, which can easily underscore the most common risks in the area.
Create a documentation portal for developers to build APIs in a secure manner.
Work closely with the security community to maintain living documents that evolve with security trends.
Project Leaders
Erez Yalon
Inon Shkedy
Paulo Silva
Licensing

The OWASP API Security Project documents are free to use!

The OWASP API Security Project is licensed under the Creative Commons Attribution-ShareAlike 4.0 license, so you can copy, distribute, and transmit the work. You can also adapt it, and use it commercially, as long as you attribute the work. If you alter, transform, or build upon this work, you may distribute the resulting work only under the same or similar license to this one.

Next
How-to Contribute
© Copyright 2023 - OWASP API Security Project team
Made with Material for MkDocs

### OWASP Top 10 API Security Risks – 2023 - OWASP API Security Top 10
Fuente: https://owasp.org/API-Security/editions/2023/en/0x11-t10/

Skip to content
OWASP API Security Top 10
OWASP Top 10 API Security Risks – 2023
Bahasa (Indonesian)
English
Français
Persian
Português (Portugal)
Initializing search
 OWASP/API-Security
Home
 
2023
 
2019
2023
Notice
Table of Contents
About OWASP
Foreword
Introduction
Release Notes
API Security Risks
OWASP Top 10 API Security Risks – 2023
API1:2023 Broken Object Level Authorization
API2:2023 Broken Authentication
API3:2023 Broken Object Property Level Authorization
API4:2023 Unrestricted Resource Consumption
API5:2023 Broken Function Level Authorization
API6:2023 Unrestricted Access to Sensitive Business Flows
API7:2023 Server Side Request Forgery
API8:2023 Security Misconfiguration
API9:2023 Improper Inventory Management
API10:2023 Unsafe Consumption of APIs
What's Next For Developers
What's Next For DevSecOps
Methodology and Data
Acknowledgments
OWASP Top 10 API Security Risks – 2023
Risk	Description
API1:2023 - Broken Object Level Authorization	APIs tend to expose endpoints that handle object identifiers, creating a wide attack surface of Object Level Access Control issues. Object level authorization checks should be considered in every function that accesses a data source using an ID from the user.
API2:2023 - Broken Authentication	Authentication mechanisms are often implemented incorrectly, allowing attackers to compromise authentication tokens or to exploit implementation flaws to assume other user's identities temporarily or permanently. Compromising a system's ability to identify the client/user, compromises API security overall.
API3:2023 - Broken Object Property Level Authorization	This category combines API3:2019 Excessive Data Exposure and API6:2019 - Mass Assignment, focusing on the root cause: the lack of or improper authorization validation at the object property level. This leads to information exposure or manipulation by unauthorized parties.
API4:2023 - Unrestricted Resource Consumption	Satisfying API requests requires resources such as network bandwidth, CPU, memory, and storage. Other resources such as emails/SMS/phone calls or biometrics validation are made available by service providers via API integrations, and paid for per request. Successful attacks can lead to Denial of Service or an increase of operational costs.
API5:2023 - Broken Function Level Authorization	Complex access control policies with different hierarchies, groups, and roles, and an unclear separation between administrative and regular functions, tend to lead to authorization flaws. By exploiting these issues, attackers can gain access to other users’ resources and/or administrative functions.
API6:2023 - Unrestricted Access to Sensitive Business Flows	APIs vulnerable to this risk expose a business flow - such as buying a ticket, or posting a comment - without compensating for how the functionality could harm the business if used excessively in an automated manner. This doesn't necessarily come from implementation bugs.
API7:2023 - Server Side Request Forge

### OWASP API Security Top 10: The 2026 Guide With Examples | HackerDNA
Fuente: https://hackerdna.com/blog/owasp-api-security-top-10

hackerdna
ETHICAL HACKING
Join for FREE
Start hacking today
Leaderboard
PLAY
Daily Hack
TODAY
Hacks
Labs
LEARN
Courses
RESOURCES
Roadmap
Refer & Earn
Free Tools
AUTHENTICATION
Login
Register
EN
Login
Register
Blog
Web Security
OWASP API Security Top 10: The 2026 Guide With Examples
WEB SECURITY
HackerDNA Team
12 min read
Jul 18, 2026

The OWASP API Security Top 10 exists because APIs break in ways classic web apps do not. A browser-facing app hides its logic behind rendered pages; an API hands you the raw endpoints, the object IDs, and the JSON, then trusts you to only ask for what is yours. That trust is exactly what attackers abuse. If you want to feel it rather than just read about it, open HackerDNA's API Security Testing course and follow along as each risk below maps to a hands-on lesson.

This list is the API-specific companion to the broader OWASP Top 10. It was rebuilt in the 2023 edition around the failures that actually show up in API penetration tests: authorization at the object level, authorization at the function level, and business logic abuse. This guide walks all ten risks with concrete examples, shows how to test for each one, and covers the defenses that hold up in production.

TL;DR: The OWASP API Security Top 10 (2023 edition) ranks the ten most critical API risks. The top three are all authorization failures: Broken Object Level Authorization (BOLA), Broken Authentication, and Broken Object Property Level Authorization. BOLA alone, where you swap one object ID for another and read data that is not yours, is the single most common serious API bug. The other seven cover resource abuse, function-level authorization, sensitive business flows, SSRF, misconfiguration, forgotten API versions, and blindly trusting third-party APIs. Learn to test each one, then lock it down with per-object authorization checks rather than trusting the client.

What Is the OWASP API Security Top 10?#

The OWASP API Security Top 10 is a standard awareness document that ranks the ten most serious security risks specific to application programming interfaces. First published in 2019 and revised in 2023, it is maintained by the OWASP API Security Project as the API-focused counterpart to the general web application list.

It exists because APIs have a different attack surface. A traditional web page couples data and presentation, so a lot of logic sits server-side and out of reach. A REST or GraphQL API strips that away: it exposes structured endpoints, predictable object identifiers, and full data objects directly to the client. The result is that the failures which matter most for APIs are not the same ones that top the web list.

Injection and cross-site scripting dominate web app testing. In API testing, the recurring finding is broken authorization: an endpoint that authenticates you correctly, then never checks whether the specific record you asked for actually belongs to you. Seven of the ten items below are, at heart, authorization problems.

💻
P

### OWASP API Security Top 10 Explained (2026) | Rohit Patil
Fuente: https://rohitpatil.com/blog/owasp-api-security-top-10-explained.html

Home
Cocktail
Games
Blogs
Tools
Search
Contact
Home
Blog
OWASP API Security Top 10
The OWASP API Security Top 10, Explained in Plain English (2026)
By Rohit Patil | Updated: July 27, 2026
Share Article
Introduction: The New Digital Front Door

In 2026, APIs are no longer just a part of the application—they are the application. They power our mobile apps, our websites, and the interconnected AI agents that define the modern web. This makes them the primary target for attackers. The Open Web Application Security Project (OWASP) maintains a critical list of the top API security risks, but the official document can be dense and academic.

This guide is different. We will break down each of the OWASP API Security Top 10 vulnerabilities with simple analogies, clear "what it is" and "how to fix it" sections, and practical code examples. Whether you're a junior backend developer or a seasoned security architect, this guide will serve as your definitive resource for building secure APIs.

API1:2026 - Broken Object Level Authorization (BOLA)
The Analogy: The Universal House Key

Imagine you have a key that opens your apartment, Unit #101. A BOLA vulnerability is like discovering that your key also opens Unit #102, #205, and every other apartment in the building. The system checked that you had a valid key, but it never checked if you were allowed to open that specific door.

What It Is

This is the most common and severe API vulnerability. It occurs when an API endpoint allows a user to access or manipulate data objects they shouldn't have permission for. The API correctly validates the user's token (they are logged in), but it fails to check if that user is the actual owner of the requested data.

Vulnerable API Request:

GET /api/v1/users/12345/profile
Copy

An attacker, logged in as user `67890`, simply changes the ID in the URL to `12345` and, if the server doesn't perform an ownership check, it will return the profile data for a different user.

How to Fix It

For every single endpoint that accesses a data record, you must implement an explicit ownership check. Never trust the ID provided by the client. Always verify it against the authenticated user's ID stored in their session or JWT.

// Node.js/Express Middleware Example
function checkOwnership(req, res, next) {
  const requestedUserId = req.params.userId;
  const authenticatedUserId = req.user.id; // From JWT

  if (requestedUserId !== authenticatedUserId) {
    return res.status(403).json({ error: "Forbidden" });
  }
  next();
}

router.get('/users/:userId/profile', authenticateToken, checkOwnership, getUserProfile);
Copy
API2:2026 - Broken Authentication
The Analogy: Leaving the Front Door Unlocked

This is a broad category that covers all the ways an attacker can bypass the login process entirely. It's like having a high-tech security system but leaving the front door unlocked, or writing the passcode on a sticky note next to the keypad.

What It Is & How to Fix It

This includes weak password

## Notas relacionadas
- [[CWE Top 25 most dangerous software weaknesses]]
- [[OWASP A04 - Diseño Inseguro]]
- [[OWASP Top 10 - Resumen]]
- [[Índice: pentesting]]
- [[Reporte de auditoría -- saas-boilerplate -- 2026-07-29]]