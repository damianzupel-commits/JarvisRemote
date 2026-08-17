---
author: jarvis
category: criptografia
created: '2026-08-13T00:01:09.526431+00:00'
tags:
- criptografia
- forense-digital
- pfa-ingreso
title: 'Hashing SHA-256 y Firma Digital: Integridad y No Repudio en Evidencia Digital'
updated: '2026-08-13T00:01:09.526431+00:00'
---

## Hashing SHA-256: integridad de la evidencia

Un algoritmo de hash criptográfico toma una entrada de cualquier tamaño (un archivo, un disco entero) y produce una salida de longitud fija (256 bits para SHA-256) que actúa como una "huella digital" del contenido. Propiedad clave para forense: **si un solo bit del contenido original cambia, el hash resultante cambia por completo** -- es prácticamente imposible producir dos entradas distintas con el mismo hash SHA-256 (resistencia a colisiones), a diferencia de MD5 o SHA-1, hoy considerados débiles para uso forense/legal por ataques de colisión conocidos.

**Uso concreto en la cadena de custodia** (ver [[Cadena de Custodia Digital]]):
1. Al adquirir la evidencia (con bloqueador de escritura), se calcula el hash SHA-256 del dispositivo original.
2. Se genera una imagen forense (copia bit a bit) y se calcula su hash.
3. Si ambos hashes coinciden, queda demostrado matemáticamente que la copia es idéntica al original.
4. En cada paso posterior de análisis, se puede recalcular el hash para demostrar que la evidencia analizada sigue siendo la misma que se recolectó -- esto es lo que sostiene la integridad de la cadena de custodia ante un tribunal.

Esto es exactamente el mecanismo que usa el módulo de investigación de Jarvis (`app/investigation/`) para dejar constancia verificable de que un artefacto no fue alterado después de registrado.

## Firma digital y criptografía asimétrica: no repudio

La firma digital usa **criptografía asimétrica** (un par de claves: privada y pública). A diferencia del hash (que prueba integridad pero no autoría), la firma digital prueba **integridad + autoría + no repudio**:

- **No repudio**: dado que solo el firmante posee la clave privada, una firma válida es prueba de que *esa* clave (y presumiblemente esa persona/sistema) generó la firma -- el firmante no puede negar de forma creíble haberla creado. Cualquiera con la clave pública correspondiente puede verificar la firma sin poder falsificarla.
- El proceso típico: se calcula el hash del documento/evidencia, y ese hash (no el documento completo) es lo que se firma con la clave privada -- eficiente y verificable.

**RSA** vs. **Ed25519** (ambos usados en el ecosistema de firma digital moderno, incluido el propio proyecto JarvisRemote para firmar artefactos/commits):

| | RSA | Ed25519 |
|---|---|---|
| Base matemática | Factorización de enteros grandes | Curva elíptica de Edwards (Curve25519), esquema EdDSA |
| Tamaño de clave | Grande (2048-4096 bits típico) | Pequeño (32 bytes) |
| Tamaño de firma | Grande | Compacto (64 bytes) |
| Velocidad | Más lento firmando/verificando | Muy rápido (>100.000 firmas/seg, >70.000 verificaciones/seg reportado) |
| Resistencia a ataques cuánticos | Vulnerable (Shor's algorithm factoriza en tiempo polinomial con computadora cuántica suficientemente potente) | También vulnerable a largo plazo, pero no es el punto de comparación típico hoy |

En la práctica forense/legal, lo relevante no es qué algoritmo es "mejor" en abstracto, sino que **la firma digital sea verificable de forma independiente** (con la clave pública, sin depender de la palabra de quien firmó) -- eso es lo que la vuelve una prueba técnica sólida de autoría y no repudio, equivalente funcional a la firma manuscrita según la propia definición que introduce en Argentina el art. 77 del Código Penal (ver [[Marco Legal Argentino: Ley 26.388 y Protocolo Federal de Evidencia Digital]]).

## Fuentes

- [Digital Forensics Master Guide: Disk Imaging, SHA-256 Hashing, Evidence Integrity -- LearnCyber](https://www.learncyber.in/2026/02/digital-forensics-master-guide-disk.html)
- [Chain of Custody for Digital Evidence: The Role of Forensic Hardware -- Ace Forensics](https://acecomputers.com/chain-of-custody/)
- [Digital Signatures -- Practical Cryptography for Developers](https://wizardforcel.gitbooks.io/practical-cryptography-for-developers-book/content/digital-signatures.html)
- [Signing and verifying messages with Ed25519: a walkthrough -- ed25519.com](https://ed25519.com/blog/signing-and-verifying-with-ed25519/)
- [Ed25519 signing -- documentación oficial de la librería `cryptography` (Python)](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/)
- [Mastering RSA Digital Signatures in Cryptography -- Number Analytics](https://www.numberanalytics.com/blog/mastering-rsa-digital-signatures-cryptography)