---
author: jarvis
category: pentesting
created: '2026-08-02T19:58:24.180702+00:00'
tags:
- investigacion
title: Supply chain security y ataques a dependencias caso xz-utils
updated: '2026-08-02T19:58:24.180702+00:00'
---

Investigación automática de Jarvis sobre "Supply chain security y ataques a dependencias caso xz-utils", basada en 4 página(s) reales visitadas.

## Fuentes

### Supply Chain Attacks: Lecciones de XZ Utils y Mas Alla | Platform Cibersecurity
Fuente: https://platform-cibersecurity.net/blog/supply-chain-attacks-lecciones-de-xz-utils-y-mas-alla/

Volver al blog
Supply Chain Attacks: Lecciones de XZ Utils y Mas Alla

Supply Chain Attacks: Lecciones de XZ Utils y Mas Alla - Analisis tecnico y guia practica por David Moya

15 de abril de 2026
•
David Moya
•
14 min read
#supply-chain
#analisis
#cti
#open-source
Compartir:

El incidente de XZ Utils en 2024 fue el equivalente a un terremoto de magnitud 9.0 en la costa de la ciberseguridad global. La ola de choque no solo inundó las líneas de costa, sino que redefinió permanentemente el mapa de amenazas para todos, desde el desarrollador solitario hasta las corporaciones del IBEX 35. Lo que muchos interpretaron como un ataque sofisticado pero aislado contra una biblioteca de compresión open-source fue, en realidad, el destello cegador que iluminó las fallas sistémicas en las que llevamos años construyendo el mundo digital. En mi experiencia, tras más de una década auditando infraestructuras críticas en España, el verdadero problema nunca es la vulnerabilidad du jour, sino la cadena de confianza rota, la visibilidad nula y la ingenua dependencia de componentes cuyo mantenimiento es, en el mejor de los casos, heroico y, en el peor, inexistente.

La realidad es que, para 2026, el ataque a la cadena de suministro (software supply chain attack) ha dejado de ser una amenaza exótica para convertirse en el vector de ataque predilecto de los grupos de amenazas persistentes avanzadas (APT) y el crimen organizado. Los datos de 2025 ya mostraban un aumento del 300% en incidentes reportados relacionados con dependencias comprometidas, y en 2026 esa tendencia no solo se ha mantenido, sino que se ha sofisticado. Ya no hablamos solo de inyectar malware en paquetes NPM o PyPI con nombres similares (typosquatting), sino de campañas de compromiso a largo plazo contra mantenedores clave, como vimos con XZ, o de la manipulación sutil de pipelines de CI/CD en plataformas como GitHub Actions o GitLab Runners para envenenar los artefactos de build desde su origen. El problema gordo aquí es que la mayoría de las empresas españolas, incluso las del sector financiero, siguen operando con un modelo de seguridad perimetral obsoleto que asume que lo interno es confiable. Cuando tu aplicación se construye con 1,500 dependencias directas y 50,000 transitivas, tu perímetro son los repositorios de código de miles de mantenedores anónimos en internet.

¿Qué nos enseñó realmente el caso XZ Utils y por qué seguimos siendo vulnerables?

La narrativa pública se centró en la ingeniería social: un atacante (o grupo) con el alias "Jia Tan" que, durante años, ganó metódicamente la confianza del mantenedor solitario de XZ, Jasak, hasta obtener permisos de commit. Esto es cierto, pero es solo la capa superficial. La lección profunda, y la que veo ignorada constantemente en las auditorías, es la del compromiso de la herramienta de construcción. El backdoor no estaba en el código fuente legible en el repositorio Git. Fue introducido a través de archivos ofuscados (.m4) que solo se activaban 

### Case Study: XZ Utils Backdoor (2024) - Open Source Software Supply Chain Security
Fuente: https://sscsecurity.dev/book1/chapter-07/ch-7.5/

Skip to content
Open Source Software Supply Chain Security
Case Study: XZ Utils Backdoor (2024)
Search
 scovetta/oss-supply-chain
Home
Book 1: Understanding
Book 2: Protecting
Book 3: Governing
Appendices
Chapter 1: How Software Is Built
1.1 How Software Is Built Today
1.2 The Role of Open Source in Modern Software
1.3 Defining the Software Supply Chain
1.4 The Trust Relationships Embedded in Software Development
1.5 Why Supply Chain Security Has Become Urgent Now
1.6 Historical Perspective: Supply Chain Attacks Aren't New
Chapter 2: The Open Source Ecosystem
2.1 A Brief History of Open Source and Its Philosophy
2.2 How Open Source Projects Are Governed and Maintained
2.3 The Maintainer Crisis
2.4 Major Package Ecosystems: A Comparative Survey
2.5 Operating System Package Managers
2.6 The Economics of Open Source
Chapter 3: The Threat Landscape
3.1 Adversary Motivations
3.2 Attack Surfaces Across the Supply Chain
3.3 The Asymmetry Problem
3.4 Cascading Risk and Blast Radius
3.5 Infrastructure as Supply Chain
Chapter 4: Threat Modeling
4.1 Supply Chain Threat Modeling Fundamentals
4.2 Threat Modeling Methodologies Applied
4.3 Identifying Crown Jewels in Your Dependency Graph
4.4 Building Attack Trees for Supply Chain Scenarios
4.5 Threat Modeling as a Continuous Practice
Chapter 5: Vulnerabilities
5.1 The Lifecycle of a Vulnerability
5.2 Case Study: Log4Shell (CVE-2021-44228)
5.3 Zero-Days vs. Known Vulnerabilities
5.4 The Patching Gap
5.5 Cryptographic Library Vulnerabilities
5.6 Memory Safety and Language-Level Vulnerabilities
Chapter 6: Package Attacks
6.1 Typosquatting and Namesquatting
6.2 Dependency Confusion Attacks
6.3 Malicious Packages
6.4 Case Studies in Package Attacks
6.5 Advanced Package Attack Techniques
6.6 Slopsquatting: AI-Hallucinated Package Attacks
Chapter 7: Build System Attacks
7.1 Compromising Build Infrastructure
7.2 Case Study: SolarWinds and the SUNBURST Attack
7.3 Case Study: 3CX Desktop App Compromise (2023)
7.4 Case Study: Codecov Bash Uploader (2021)
7.5 Case Study: XZ Utils Backdoor (2024)
7.6 CI/CD Pipeline Vulnerabilities
7.7 Code Signing and Its Limitations
7.8 Attacks on Distribution Channels
7.9 Case Study: Notepad++ Update Hijacking (2025)
Chapter 8: Insider Threats and Social Engineering
8.1 Compromised Maintainer Accounts
8.2 Malicious Commits and Pull Requests
8.3 Social Engineering Targeting Maintainers
8.4 Insider Threats in Open Source Projects
8.5 Git-Specific Attack Vectors
8.6 Fake Security Researchers and Malicious Fixes
Chapter 9: Ecosystem-Specific Supply Chains
9.1 Mobile Application Supply Chains
9.2 Browser Extension Supply Chains
9.3 Content Management System Ecosystems
9.4 Client-Side JavaScript and CDN Supply Chains
9.5 Serverless and Function-as-a-Service Supply Chains
9.6 Infrastructure-as-Code Supply Chains
Chapter 10: Emerging Threats
10.1 AI Coding Assistants and Supply Chain Risk
10.2 Package Hallucination and Slopsquatting
10.3 AI Coding Agents and Autonomous Development
10.4 Model Con

### XZ Utils Backdoor Analysis: Anatomy of an Attack
Fuente: https://safeguard.sh/resources/blog/the-xz-utils-backdoor-anatomy-of-a-supply-chain-attack

Skip to content
Models
Platform
Use Cases
Solutions
Resources
Company
Download
Book a call
Login
BLOG
/
INCIDENT ANALYSIS
INCIDENT ANALYSIS
•
NOVEMBER 8, 2025
The XZ Utils backdoor: anatomy of a supply chain attack

A two-year maintainer-trust takeover placed a pre-auth SSH backdoor inside xz-utils. Heres how CVE-2024-3094 was built, hidden, and caught in time.

J
James
Principal Security Architect
November 8, 2025
7 min read
Share
ON THIS PAGE
A Multi-Year Infiltration, Not a Hack
How the Backdoor Actually Worked
The Blast Radius That Almost Was
What Every Security Team Should Take Away
How Safeguard Helps

MARCH 29, 2024 — A Microsoft engineer debugging unrelated performance complaints in PostgreSQL noticed something odd: SSH logins on a development box were consuming an extra 500 milliseconds of CPU time and tripping up Valgrind. That half-second anomaly, caught by Andres Freund almost by accident on a Good Friday afternoon, unraveled what is now widely regarded as the most sophisticated open-source supply chain attack ever documented — a backdoor planted inside xz-utils, a compression library that ships in nearly every Linux distribution on Earth. The flaw, tracked as CVE-2024-3094 and scored a maximum 10.0 on the CVSS scale, was the product of what researchers now believe was at least two to three years of patient, methodical social engineering by an attacker operating under the alias "Jia Tan." Had it not been caught in the narrow window between its introduction in versions 5.6.0/5.6.1 and its arrival in stable Linux releases, the backdoor would have granted a remote attacker pre-authentication code execution over SSH on an enormous swath of internet-facing infrastructure.

A Multi-Year Infiltration, Not a Hack

What makes the XZ Utils incident a watershed moment for the security industry isn't the exploit primitive itself — it's the tradecraft used to get it there. This was not a compromised credential, a leaked signing key, or a scanner miss. It was a deliberate, patient takeover of a maintainer's trust.

The xz-utils project had, for years, been maintained largely by a single volunteer, Lasse Collin, in the classic pattern of critical open-source infrastructure: enormous downstream reach, minimal maintainer bandwidth. Beginning around 2021, an account using the name "Jia Tan" began submitting legitimate, useful patches to the project. Over roughly two years, this persona built a credible commit history, engaged constructively on mailing lists, and was gradually granted co-maintainer status and commit access. Investigators later identified a supporting cast of sockpuppet accounts that applied social pressure on the original maintainer — filing complaints, pushing for faster releases, and lobbying for "Jia Tan" to be given greater responsibility, ostensibly to relieve maintainer burnout. It is a pattern security teams should recognize immediately: it mirrors reconnaissance and grooming techniques more commonly associated with nation-state 

### La Nueva Amenaza Invisible: Los Ataques a la Cadena de Suministro de Software Más que Se Duplican en 2025 | The New Times
Fuente: https://www.thenewtimes.tech/es/seguranca-risco/ataques-cadeia-fornecimento-software-supply-chain-2026

MARTES, 28 DE JULIO DE 2026
PT
·
EN
·
DE
·
ES
The New Times
INTELIGENCIA TECNOLÓGICA
Estrategia
Seguridad y Riesgo
Regulación
Mercados
Liderazgo
Contacto
←
ANÁLISIS PRINCIPAL
SEGURIDAD Y RIESGO
7 min
5 de mayo de 2026
La Nueva Amenaza Invisible: Los Ataques a la Cadena de Suministro de Software Más que Se Duplican en 2025

Los incidentes de la cadena de suministro de software más que se duplicaron a nivel global en 2025, exponiendo brechas críticas en la preparación empresarial. El ataque a tj-actions en marzo de 2025 comprometió pipelines CI/CD en miles de repositorios. El caso de XZ Utils de 2024, donde un atacante pasó dos años construyendo confianza antes de insertar un backdoor, definió el estándar de la amenaza moderna.

El ataque que definió el estándar de la amenaza moderna de la cadena de suministro de software no fue rápido. Fue paciente. Durante más de dos años, un actor desconocido contribuyó regularmente a XZ Utils, una herramienta de compresión de Linux presente en prácticamente todas las distribuciones del sistema operativo. Ganó la confianza de la comunidad, obtuvo acceso de mantenedor y, en marzo de 2024, insertó un backdoor cuidadosamente diseñado en las versiones oficiales del proyecto. El descubrimiento fue accidental: un ingeniero de Microsoft notó un comportamiento anómalo de rendimiento antes de que el código malicioso llegara a las distribuciones de producción.




XZ Utils no fue el pico. Fue el precedente.



Los Incidentes de 2025



En marzo de 2025, el compromiso de tj-actions, una herramienta ampliamente utilizada en pipelines de integración continua en GitHub, demostró que el riesgo de CI/CD no es teórico. Secretos fueron expuestos a través de un volcado de memoria en tiempo de ejecución en miles de repositorios que utilizaban la herramienta.




En agosto de 2025, versiones maliciosas del paquete Nx incluyeron scripts de post-instalación que barrían sistemas afectados en busca de tokens, claves SSH y secretos de API, exfiltrando los datos a repositorios controlados por los atacantes. En septiembre, la campaña TinyColor inyectó scripts maliciosos en el popular paquete de colores y decenas de paquetes relacionados, transformándolos en un gusano autorreplicante que recogía credenciales durante la instalación.




Los incidentes de la cadena de suministro de software más que se duplicaron a nivel global en 2025, según investigadores de seguridad que monitorean repositorios públicos y privados.



La Diferencia Estructural en Relación al Ataque Convencional



En un ataque convencional, el adversario intenta invadir el perímetro de la organización. En el ataque a la cadena de suministro, el adversario compromete algo en lo que la organización ya confía. La diferencia es fundamental: los controles de detección y respuesta que protegen el perímetro son ineficaces contra el código malicioso que entra como una actualización legítima de una dependencia.




SolarWinds demostró esto en 2020 con 18,000 organizaciones instaland

## Notas relacionadas
- [[Reporte de auditoría -- pygoat -- 2026-07-29]]
- [[Defensa en Profundidad]]
- [[Herramientas SAST y SCA - Resumen]]
- [[Snyk en la Práctica]]
- [[CWE Top 25 most dangerous software weaknesses]]
- [[Índice: pentesting]]