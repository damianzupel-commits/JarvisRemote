---
author: jarvis
category: inteligencia-de-amenazas
created: '2026-08-17T00:00:00.000000+00:00'
tags:
- inteligencia-de-amenazas
- mitre-attack
- acceso-a-credenciales
- deteccion
- defensa
title: 'ATT&CK Acceso a Credenciales - Detección y Defensa'
updated: '2026-08-17T00:00:00.000000+00:00'
---

Táctica **TA0006**. Parte de [[Inteligencia de Amenazas: Índice y Mapa (Detección y Defensa)]]. Cómo el adversario **roba usuarios y contraseñas** para moverse sin explotar más nada. Relacionado: [[Gestion segura de contrasenas hashing bcrypt argon2 salting]].

## T1003 — OS Credential Dumping (LSASS, SAM, /etc/shadow, NTDS.dit)
**Qué es.** Extraer credenciales del propio SO: memoria de LSASS, hive SAM, `/etc/shadow`, base de dominio `NTDS.dit`.
**Uso del adversario (conceptual).** Vuelca la memoria del proceso que guarda credenciales o copia los almacenes offline para crackear/reutilizar hashes. *(No se documenta el procedimiento; el foco es la detección.)*
**Detección.** Acceso a LSASS por procesos que no son del sistema (Sysmon 10 con GrantedAccess sospechoso a `lsass.exe` — de las señales más valiosas); copia de SAM/SECURITY hives; acceso a `ntds.dit`/`vssadmin` en DC; lectura de `/etc/shadow` por proceso no-root habitual.
**Mitigación/endurecimiento.** **Credential Guard** (aísla LSASS en VBS); LSASS como Protected Process Light (PPL); Attack Surface Reduction rule "block credential stealing from LSASS"; mínimo privilegio; no reutilizar contraseñas de admin local (LAPS).
**Prueba atómica.** Atomic Red Team T1003.001 intenta volcar la memoria de LSASS con métodos conocidos (procdump, comsvcs) para verificar que tu EDR/ASR lo bloquea o alerta.

## T1555 — Credentials from Password Stores (navegadores, keychain, gestores)
**Qué es.** Robar credenciales guardadas: bases de logins de navegadores Chromium, Windows Credential Manager, keychains.
**Detección.** Acceso a `\Chrome\User Data\...\Login Data` y `Local State` por procesos no-navegador; lectura del Credential Manager.
**Capacidad Jarvis.** La regla `Browser_Credential_Store_Access` de `starter.yar` matchea exactamente estas rutas y el SQL de robo (`SELECT origin_url, username_value, password_value`) — es un infostealer clásico (ver [[Familias de Malware - Taxonomía Detección y Defensa]], categoría spyware/stealer).
**Mitigación.** No guardar contraseñas en el navegador para cuentas críticas; gestor de contraseñas dedicado; cifrado de disco; EDR.

## T1110 — Brute Force (password spraying, credential stuffing)
**Qué es.** Probar contraseñas por fuerza bruta, spraying (una clave contra muchas cuentas) o stuffing (credenciales filtradas).
**Detección.** Muchos logins fallidos (Windows 4625) contra una o muchas cuentas; picos desde una IP; bloqueos de cuenta en masa.
**Mitigación.** MFA (mata el 99% de esto); lockout progresivo; detección de contraseñas filtradas; bloqueo por reputación de IP.
**Prueba atómica.** Atomic Red Team T1110 ejecuta intentos controlados para validar el umbral de alerta de logins fallidos.

## T1558 — Steal or Forge Kerberos Tickets (Kerberoasting, Golden/Silver Ticket)
**Qué es.** Abusar de Kerberos: pedir tickets de servicio para crackearlos offline (Kerberoasting), o forjar tickets con la clave krbtgt.
**Detección.** Muchas solicitudes de TGS (Windows 4769) con cifrado débil (RC4); tickets con vida anómala; uso de cuentas de servicio con SPN.
**Mitigación.** Contraseñas largas y aleatorias en cuentas de servicio (gMSA); AES en lugar de RC4; rotación de krbtgt; monitoreo de 4769.

## T1552 — Unsecured Credentials (en archivos, historial, código)
**Qué es.** Credenciales en texto plano: archivos de config, variables de entorno, historial de shell, código fuente, `.aws/credentials`.
**Detección.** Acceso masivo a archivos de config/`.env`; grep de secretos por procesos anómalos. Enlaza con [[Secretos Hardcodeados en Código]] y [[Gestión de Secretos]].
**Mitigación.** Vault de secretos; escaneo de secretos en repos (ver [[Herramientas SAST y SCA - Resumen]]); mínimo privilegio; no loguear secretos.

## Referencias
- MITRE ATT&CK TA0006 (Credential Access).
- Microsoft — Credential Guard, LAPS, ASR "block credential stealing from LSASS".
- Atomic Red Team — atomics T1003.*, T1555.*, T1110, T1558.*.
