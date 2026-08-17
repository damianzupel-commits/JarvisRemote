# CYBER-RANGE-DESIGN.md — Laboratorio de pentesting aislado para probar Jarvis

> Documento de diseño (no ejecutable). Describe cómo montar un **cyber range**
> cerrado, en la PC de Damian, para probar de forma agresiva los módulos
> ofensivos de Jarvis (nmap, SQLMap, ZAP, Wireshark/scapy, Metasploit) contra
> blancos deliberadamente vulnerables que son **propiedad de Damian**, sin
> ninguna posibilidad de tocar sistemas de terceros.
>
> Creado: 2026-08-17. Alcance: solo el diseño. **No instala ni ejecuta nada.**
> Antes de ejecutarlo, revisar y ajustar tamaños de disco según el espacio libre
> real (ver §4, que no está confirmado).

---

## 1. Resumen y regla de oro

El objetivo es un banco de pruebas ofensivo **totalmente aislado**: una red
virtual sin salida a internet, con una VM atacante (Kali + Jarvis apuntando a
ella) y varias VMs blanco fabricadas para ser vulneradas. Se ataca, se rompe, se
restaura desde snapshot y se repite.

**Regla de oro (corta, tres puntos, no negociable):**

1. **Todo blanco es propiedad de Damian o una imagen hecha a propósito para ser
   vulnerada** (Metasploitable, DVWA, Juice Shop, VulnHub, etc.). Nada externo.
2. **La red del lab no tiene salida a internet ni ruta hacia la LAN real ni hacia
   WSL2.** El aislamiento es de red, no de buena voluntad: se implementa con red
   *host-only/interna* (§3).
3. **`backend/authorized_targets.yaml` de Jarvis es el control técnico de scope.**
   Solo Damian lo edita a mano; ni las tools ni el LLM pueden escribirlo (ya está
   así por diseño). El range vive dentro de un rango IP privado que Damian agrega
   explícitamente a ese archivo. Fuera de ese rango, las tools de pentest activo
   se niegan a correr.

Con esos tres controles superpuestos (red aislada + blancos propios + gate de
`authorized_targets.yaml`), atacar "a lo bruto" es un uso legítimo de seguridad
ofensiva estilo laboratorio OSCP.

---

## 2. Plataforma de virtualización y la decisión Hyper-V / WSL2

### 2.1 VMware Workstation Pro vs VirtualBox (estado 2026)

- **VMware Workstation Pro es gratis** para uso personal, educativo y comercial
  desde que Broadcom lo liberó (nov. 2024). Solo hace falta una cuenta gratuita de
  Broadcom para descargarlo. Ya no hay razón de licencia para preferir VirtualBox.
- **Snapshots** (lo más importante para un range donde se rompen VMs a propósito):
  VMware tiene el árbol de snapshots más pulido, restauración confiable en cadenas
  complejas y snapshots automáticos programados (cada 30 min / 1 h / 1 día) con
  poda de los viejos. VirtualBox tiene árbol de snapshots correcto pero **sin**
  auto-snapshot integrado (habría que scriptear `VBoxManage`).
- **Performance de I/O**: VMware Workstation lleva ventaja grande en disco (varias
  veces más throughput/IOPS de NVMe que VirtualBox 7.x en el mismo hardware).
- **VirtualBox** sigue siendo la opción más simple y 100% libre para arrancar, e
  importa OVA/OVMF de VulnHub sin fricción.

### 2.2 El conflicto real: Hyper-V/WSL2 vs los hipervisores tipo 2

El punto crítico de esta PC: **Damian usa WSL2 para Jarvis, y WSL2 corre sobre
Hyper-V** (una utility VM liviana de Hyper-V). Para tener WSL2 hay que tener
activadas las plataformas de virtualización de Windows (Hyper-V / *Windows
Hypervisor Platform* / *Virtual Machine Platform*).

Históricamente eso peleaba con VMware/VirtualBox: si Hyper-V se adueñaba del
procesador (era el hipervisor "raíz"), VMware/VBox no podían usar VT-x directo y
fallaban o iban lentísimos. Ese es el conflicto clásico.

**Estado 2026 — ya está resuelto, con un costo:**

- VMware Workstation moderno (16+, y muy pulido en las builds actuales) puede
  **coexistir con Hyper-V** montándose sobre la **Windows Hypervisor Platform
  (WHP)**. Los dos hipervisores comparten el backend de Hyper-V. Igual para
  VirtualBox reciente, que también soporta el modo WHP.
- **Costo**: al no usar VT-x nativo directo sino la capa WHP, las VMs de
  VMware/VBox pierden algo de rendimiento (capa de traducción). Para un lab de
  pentest — donde los blancos son livianos y lo que importa es la red y las
  herramientas, no exprimir CPU — ese costo es perfectamente asumible.

**Aclaración importante:** el lab **no necesita virtualización anidada**. Kali,
Metasploitable, DVWA, etc. son guests normales; nadie corre un hipervisor *dentro*
de un guest. La penalización relevante acá es solo la de correr VMware sobre WHP,
no la de anidar hipervisores.

### 2.3 Recomendación para ESTE caso

**Usar VMware Workstation Pro (gratis) en modo coexistencia con Hyper-V/WHP,
manteniendo WSL2 encendido.** Fundamentos:

- Es gratis, tiene la mejor gestión de snapshots (auto-snapshots, restauración
  confiable) — que es exactamente el bucle central de este range — y la mejor I/O.
- Coexiste con WSL2 sin apagar Hyper-V, así que **Jarvis en WSL2 sigue
  funcionando** mientras el lab está levantado. No hay que elegir entre "tener
  Jarvis" y "tener el lab".
- El único costo es una merma de rendimiento en las VMs del lab, irrelevante para
  blancos livianos.

**Cuándo elegir la alternativa (VirtualBox):** si por algún motivo VMware sobre
WHP diera problemas de estabilidad en esta máquina, VirtualBox reciente en modo
WHP es el plan B; es 100% libre e importa OVAs de VulnHub sin fricción, a costa de
snapshots menos cómodos y menor I/O.

**Lo que NO se recomienda:** apagar Hyper-V (`bcdedit /set hypervisorlaunchtype
off`) para darle VT-x nativo a VMware. Eso maximiza el rendimiento del lab pero
**mata WSL2** y por lo tanto a Jarvis. Va en contra del objetivo. Se deja
documentado solo como conocimiento, no como recomendación.

---

## 3. Topología de red del laboratorio

La idea es una **red aislada** donde viven todos los blancos y la interfaz de
ataque de Kali, **sin salida a internet ni ruta hacia la LAN doméstica ni hacia
la subred de WSL2**.

### 3.1 Tipo de red

- En VMware: usar una **red host-only** o, mejor para máximo aislamiento, una
  **red "LAN segment"** (segmento privado que ni siquiera el host rutea a
  internet). En VirtualBox el equivalente es **"Internal Network"** (aislamiento
  total) o **"Host-Only"** (el host la ve, pero sin NAT a internet).
- **No usar NAT ni Bridged en la interfaz de ataque.** NAT daría salida a internet
  a los blancos; Bridged los pondría en la LAN real de Damian. Ambos rompen el
  aislamiento.
- Sin DHCP hacia internet: IPs estáticas o un DHCP acotado al propio segmento.

### 3.2 Rango IP sugerido

Elegir un rango privado **que no choque** con la LAN doméstica ni con la subred de
WSL2 (WSL2 suele usar `172.x` internos). Sugerencia deliberadamente distinta:

```
Red del range:      10.13.37.0/24   (máscara 255.255.255.0)
Gateway ficticio:   10.13.37.1      (no existe / sin ruta a internet)
Kali (atacante):    10.13.37.10
Blancos:            10.13.37.20 – 10.13.37.99
```

Este `10.13.37.0/24` es el rango que Damian agrega a `authorized_targets.yaml`
(ver §6). Al ser privado y aislado, cumple la política por defecto de Jarvis
(solo rangos privados/loopback/Tailscale).

### 3.3 Doble interfaz opcional en Kali

Si Damian quiere que Kali tenga internet (para actualizar herramientas) **sin**
darle internet a los blancos, se le ponen **dos placas** a Kali:

- **eth0** → red aislada del range (host-only/interna) — la que usa para atacar.
- **eth1** → NAT (solo para `apt update` de Kali) — **apagada durante los
  ataques**, o con reglas para no reenviar tráfico entre placas.

Los **blancos nunca** tienen la placa NAT: una sola interfaz, la del segmento
aislado. Así un blanco comprometido no tiene por dónde salir.

### 3.4 Diagrama (ASCII)

```
                 HOST Windows 11 (Ryzen 5 5600X / 32 GB / RX 6700 XT)
                 Hyper-V/WHP activo  ──►  WSL2  ──►  Jarvis backend
                 │
                 │   (VMware Workstation Pro sobre WHP)
                 │
   ┌─────────────┴───────────────────────────────────────────────┐
   │                RED AISLADA DEL RANGE  10.13.37.0/24           │
   │              (host-only / LAN segment — SIN internet)         │
   │                                                               │
   │   ┌───────────────┐                                           │
   │   │ Kali atacante │ .10   eth0 = range        (eth1 = NAT,    │
   │   │  + Jarvis apunta│                           apagada en     │
   │   │    aquí        │                            ataques)       │
   │   └───────┬───────┘                                           │
   │           │  ataca ──►                                        │
   │           ▼                                                   │
   │   ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
   │   │ DVWA     │  │Juice Shop│  │Metasploit│  │ Windows viejo │  │
   │   │ .20      │  │ .21      │  │able .30  │  │ (SMB) .40     │  │
   │   └──────────┘  └──────────┘  └──────────┘  └──────────────┘  │
   │        (blancos: 1 sola placa, sin ruta a internet)           │
   └───────────────────────────────────────────────────────────────┘

   LAN doméstica real  ✗  (sin ruta desde el segmento del range)
   Subred de WSL2       ✗  (rango IP distinto, sin puente)
```

El aislamiento queda garantizado por: (a) tipo de red host-only/interna sin NAT en
los blancos, (b) rango IP que no colisiona con LAN ni WSL2, (c) Jarvis limitado
por `authorized_targets.yaml` a `10.13.37.0/24`.

---

## 4. Presupuesto de recursos (32 GB RAM, 6c/12t)

Regla práctica: **dejar ~8 GB para Windows + WSL2/Jarvis**, y repartir el resto
entre las VMs. Con 32 GB alcanza para un set "cómodo" simultáneo y, aparte, para
correr blancos pesados de a uno.

> ⚠️ **Espacio libre exacto sin confirmar.** El host tiene **tres SSD de 480 GB**
> (dos Kingston SATA + un M.2 NVMe); se asume 480 GB por unidad. Los tamaños de
> abajo son la huella típica de cada VM. El reparto entre discos está en §4.4.
> Total del set cómodo ≈ **90–110 GB** de VMs activas.

### 4.1 Set "cómodo" — todo prendido a la vez

| VM                       | vCPU | RAM      | Disco aprox. | Notas |
|--------------------------|------|----------|--------------|-------|
| Windows host + WSL2/Jarvis | (host) | ~8 GB reservada | — | No es VM; es el host + Jarvis |
| Kali (atacante)          | 2–4  | 4 GB     | 40–80 GB     | Sube a 6 GB si corre muchas tools |
| Metasploitable 2 (Linux) | 1    | 512 MB–1 GB | 8 GB      | Livianísimo |
| DVWA (contenedor/VM)      | 1    | 1 GB     | 2–10 GB      | Ideal como contenedor en Kali/target |
| OWASP Juice Shop          | 1    | 1–2 GB   | 2–5 GB       | Node; también contenedor |
| **Total en uso**         | ~6   | **~15–16 GB** | ~60–105 GB | Deja ~16 GB de RAM libre |

Este set entra holgado en 32 GB y en 6 núcleos.

### 4.2 Set "pesado" — de a uno por vez

| VM                          | vCPU | RAM     | Disco aprox. | Notas |
|-----------------------------|------|---------|--------------|-------|
| Metasploitable 3 (Windows)  | 2    | 4 GB    | 40–60 GB     | Pesado; usar snapshot |
| Windows 7 / Server 2008 (SMB/EternalBlue) | 2 | 2–4 GB | 30–40 GB | Blanco de RCE de SMBv1 |
| VulnHub grande (varía)      | 1–2  | 1–4 GB  | 10–40 GB     | Según la máquina |

Correr **uno de estos a la vez** junto con Kali (4 GB) y el host (8 GB) queda muy
por debajo de 32 GB. No apilar dos blancos pesados de Windows simultáneamente.

### 4.3 Consejo de asignación

- **No sobre-asignar vCPU**: con 12 hilos, dar 2 vCPU a cada VM activa y no pasar
  de ~8 vCPU repartidos, para que el host y WSL2 respiren.
- Preferir **contenedores** (DVWA, Juice Shop, catálogo *vulhub*) dentro de una VM
  Linux liviana antes que una VM por cada app web: ahorra RAM y disco.
- Discos **dinámicos/thin** para no reservar el máximo de entrada.

### 4.4 Reparto de discos (3 × SSD 480 GB)

El host tiene tres SSD de 480 GB: **dos Kingston SATA** y **uno M.2 NVMe**. La idea
es poner lo que se beneficia de velocidad en el NVMe y lo que solo necesita
capacidad en el SATA. El NVMe es varias veces más rápido en I/O aleatorio, y en un
range los cuellos de botella típicos son el arranque de VMs y la creación/reversión
de snapshots — todo I/O.

**Disco 1 — M.2 NVMe (480 GB): VMs "activas".**
Kali (atacante) + el **blanco en curso** + el estado de trabajo de Jarvis. Es lo
único que corre a la vez y lo que más se beneficia de la velocidad. También conviene
que la VM contra la que estás iterando (snapshots PRE/POST frecuentes) viva acá,
porque revertir es una operación de disco intensiva.

| Contenido en el NVMe            | Disco aprox. |
|---------------------------------|--------------|
| Kali + snapshots de trabajo     | 60–100 GB    |
| Blanco en curso (1 pesado o varios livianos) | 40–80 GB |
| Margen para snapshots PRE/POST activos | 40–80 GB |
| **Objetivo de uso**             | **≤ 300 GB (dejar ~180 GB libres)** |

**Disco 2 — Kingston SATA #1 (480 GB): biblioteca de blancos + almacén de imágenes.**
Todas las VMs blanco que **no** están corriendo ahora, los OVA/imágenes originales
descargadas (Metasploitable 2/3, VulnHub, ISOs de Windows viejo) y los
**snapshots BASE-limpio** de cada blanco. Nada de esto necesita la velocidad del
NVMe: se lee al importar/clonar y punto. Cuando toca atacar un blanco nuevo, se
**clona** desde acá al NVMe, se ataca, y al terminar se borra la copia del NVMe (el
original y su BASE quedan intactos en el SATA).

| Contenido en el SATA #1         | Disco aprox. |
|---------------------------------|--------------|
| OVAs/ISOs originales (biblioteca) | 80–150 GB  |
| Snapshots BASE-limpio de todos los blancos | 100–200 GB |
| **Objetivo de uso**             | **≤ 380 GB (dejar ~100 GB libres)** |

**Disco 3 — Kingston SATA #2 (480 GB): margen / expansión / sistema.**
Reserva. Usos posibles: overflow cuando la biblioteca crece, exports de casos para
análisis forense, o mover acá el sistema/pagefile si el NVMe se llena. Mantenerlo
mayormente libre da aire para picos de snapshots sin frenar el lab.

**Aclaración de capacidad:** 480 GB por unidad alcanza para un lab sólido, **pero
no es infinito**. El que más rápido se llena es el NVMe, y el que más engaña es el
SATA de la biblioteca, porque **los snapshots crecen** con cada cambio en la VM.

### 4.5 Convención anti-llenado de snapshots

Los snapshots no son gratis: cada uno guarda el *delta* desde el anterior, y una
cadena larga sobre una VM que se ataca mucho puede inflarse a decenas de GB sin que
te des cuenta. Regla de higiene:

- **Tamaño estimado por snapshot:** blanco Linux liviano (Metasploitable 2, DVWA)
  ≈ 1–5 GB por snapshot; blanco Windows (Metasploitable 3, Win7 SMB) ≈ 5–20 GB por
  snapshot según lo que se altere. Cadenas de 4–5 snapshots sobre un Windows pueden
  fácilmente pasar los 50 GB.
- **Un solo BASE por blanco, y es sagrado** (vive en el SATA #1, nunca se borra).
- **Los PRE/POST son desechables:** apenas terminás de analizar un ataque, revertí
  al BASE y **borrá los PRE/POST** de esa sesión. No acumular árboles largos.
- **Regla del "máx. 3":** no tener más de ~3 snapshots vivos por VM al mismo tiempo.
  Si necesitás más historia, consolidá (merge) hacia el BASE o exportá una copia.
- **Kali es la excepción:** ahí sí acumulás estado útil (loot, notas), pero igual
  podá auto-snapshots viejos periódicamente.
- **Revisá el uso del NVMe una vez por sesión.** Si baja de ~100 GB libres, es señal
  de limpiar PRE/POST y borrar clones de blancos ya terminados.

---

## 5. Los blancos, de suave a brutal

Ordenados por agresividad creciente y mapeados a la técnica y a la tool de Jarvis
que ejercitan.

### 5.1 Suave — web / inyección (capa 7)

- **DVWA (Damn Vulnerable Web Application)** — dificultad ajustable. SQLi, XSS,
  CSRF, command injection, file upload. **Ejercita:** SQLMap (inyección SQL),
  ZAP (spider + scan pasivo/activo web) y el módulo de formularios de Jarvis.
  Es el mejor primer blanco: subís la dificultad de "low" a "impossible" a medida
  que Jarvis mejora.
- **OWASP Juice Shop** — app moderna (Node/Angular), catálogo enorme de retos
  (OWASP Top 10 actual, JWT, NoSQL, etc.). **Ejercita:** ZAP contra una SPA real,
  fuzzing de API, y la lógica de recon web de Jarvis. Más "2026" que DVWA.

### 5.2 Medio — explotación de servicios de red (Linux)

- **Metasploitable 2** — Linux vulnerable clásico: servicios viejos (vsftpd con
  backdoor, Samba, distccd, UnrealIRCd, PostgreSQL/MySQL débiles, Tomcat).
  **Ejercita:** nmap (descubrimiento + versiones + scripts NSE), Metasploit
  (exploits de servicio → shell), Wireshark/scapy (ver el tráfico del ataque).
  Es el campo de tiro ideal para el flujo recon → exploit → shell.
- **Catálogo *vulhub*** (contenedores por CVE) — decenas de entornos Docker cada
  uno reproduciendo una CVE concreta (Struts, Log4Shell, Confluence, etc.).
  **Ejercita:** explotación dirigida por CVE puntual; excelente para probar que
  Jarvis identifica y explota una vulnerabilidad *específica*.

### 5.3 Fuerte — Windows y RCE de SMB

- **Windows 7 / Server 2008 con SMBv1 (MS17-010 / EternalBlue)** — VM Windows
  vieja, sin parchear, SMBv1 encendido. **Ejercita:** el scanner
  `auxiliary/scanner/smb/smb_ms17_010`, el exploit
  `exploit/windows/smb/ms17_010_eternalblue` → Meterpreter, y toda la fase de
  **post-explotación** en Windows (migración de proceso, hashes, pivote).
  Es RCE no autenticado: el salto de "web" a "tomar la caja entera".
- **Metasploitable 3 (Windows)** — versión moderna, entorno Windows con múltiples
  servicios vulnerables y "flags". **Ejercita:** cadena completa recon → exploit →
  post-explotación en un Windows más realista que un XP/7 pelado.

### 5.4 Brutal — máquinas VulnHub estilo OSCP + estrés

- **Máquinas de VulnHub** (OVA importable) — dificultad "OSCP-like": encadenar
  varias vulns, escalar privilegios, moverse. **Ejercita:** el pipeline completo
  de Jarvis de punta a punta, sin pistas.
- **Pruebas de DoS / captura pesada** (solo contra blancos del range) — saturar un
  servicio, floods, captura masiva de paquetes. **Ejercita:** scapy/captura de
  Jarvis y el comportamiento bajo estrés. **Reservado a la última fase** (§8) y
  **solo** dentro de `10.13.37.0/24`.

Progresión sugerida: **DVWA → Juice Shop → Metasploitable 2 → vulhub por CVE →
Windows SMB/EternalBlue → Metasploitable 3 → VulnHub OSCP → estrés/DoS.**

---

## 6. Cómo se conecta Jarvis al range

### 6.1 Dónde corre qué

- **Jarvis** sigue donde está: backend en WSL2/Windows, con sus tools ofensivas
  (nmap, SQLMap, ZAP, scapy, y la delegación a Metasploit).
- La **VM Kali** es la plataforma de ejecución de las herramientas pesadas
  (Metasploit, ZAP GUI, etc.) y el punto de red desde el que se ataca. Jarvis
  **apunta sus ataques a las IPs del range** (`10.13.37.20+`).
- Para que Jarvis (en WSL2) alcance el segmento aislado hay dos variantes:
  1. **Jarvis orquesta a Kali:** Jarvis abre sesión/comandos en la VM Kali (SSH a
     `10.13.37.10` a través de una interfaz que el host comparta con el segmento)
     y desde Kali lanza nmap/Metasploit/etc. Es lo más limpio: el tráfico de
     ataque nace *dentro* del range.
  2. **Jarvis ataca directo:** si el host expone la red host-only a WSL2, Jarvis
     corre sus tools nativas contra las IPs del range. Requiere verificar que la
     ruta host-only ↔ WSL2 no abra un agujero al resto; preferir la variante 1
     para mantener el aislamiento estricto.

**Recomendación:** variante 1 (Jarvis → Kali → blancos). Mantiene todo el tráfico
ofensivo dentro del segmento y a Jarvis como orquestador.

### 6.2 Agregar el range a `authorized_targets.yaml`

Antes del primer ataque, Damian (a mano — ni Jarvis ni las tools pueden escribir
ese archivo) agrega el rango del lab. Conceptualmente:

```yaml
# backend/authorized_targets.yaml  (editar SOLO a mano)
authorized:
  - cidr: 10.13.37.0/24
    label: "cyber-range-local"
    note: "Lab aislado, blancos propios. Alta 2026-08-17."
```

Con eso, las tools de pentest activo (nmap/sqlmap/ZAP/captura) validan el target
contra el archivo y **solo** disparan si cae dentro de `10.13.37.0/24`. Cualquier
IP fuera del range → la tool se niega. Ese es el gate de scope funcionando a favor.

### 6.3 Qué tool de Jarvis se ejercita en cada fase

| Fase                | Tools de Jarvis                                   | Blanco típico |
|---------------------|---------------------------------------------------|---------------|
| Recon / descubrimiento | `network_scan` (nmap pasivo), lectura de servicios | todo el /24 |
| Escaneo web         | ZAP (spider/scan), `web_forms`/formularios        | DVWA, Juice Shop |
| Inyección SQL       | SQLMap                                             | DVWA |
| Explotación servicio | Metasploit (vía delegación), nmap NSE            | Metasploitable 2/3, vulhub |
| RCE SMB             | Metasploit `ms17_010_*`                            | Windows SMB |
| Post-explotación    | shell/Meterpreter, `pc_command` en el blanco       | Windows, VulnHub |
| Tráfico / captura   | scapy / captura de paquetes                        | cualquiera |

---

## 7. Flujo de snapshots (el bucle central)

La razón de existir del range: romper VMs sin miedo, porque volver atrás cuesta un
click. **Snapshot base de cada blanco antes de tocarlo**, atacar, y restaurar.

### 7.1 Convención de nombres

```
<blanco>-BASE-limpio          → estado recién instalado, servicios arriba, sin tocar
<blanco>-PRE-<tecnica>-<fecha> → justo antes de un ataque concreto
<blanco>-POST-<tecnica>-<fecha>→ estado comprometido, para análisis forense
```

Ejemplos: `metasploitable2-BASE-limpio`, `win7smb-PRE-eternalblue-20260817`,
`dvwa-POST-sqli-20260817`.

### 7.2 El bucle "atacar → romper → restaurar → repetir"

1. **Snapshot BASE** de cada blanco apenas queda instalado y funcionando. Este es
   el ancla; nunca se borra.
2. (Opcional) **Snapshot PRE** antes de una técnica específica, para aislar el
   efecto de ese ataque.
3. **Jarvis ataca.** Se rompe el blanco (shell, servicio caído, disco alterado).
4. (Opcional) **Snapshot POST** si querés analizar el estado comprometido después.
5. **Restaurar al BASE** (o al PRE) con un click. El blanco vuelve limpio.
6. **Repetir** con otra técnica o con Jarvis "mejorado".

### 7.3 Buenas prácticas

- Aprovechar los **auto-snapshots programados** de VMware para Kali (que sí
  acumula estado útil: notas, loot), pero **no** para los blancos, que se resetean
  al BASE.
- La VM Kali se snapshotea también en un `kali-BASE` por si una herramienta la deja
  inconsistente.
- Documentar en una nota de Obsidian de Jarvis qué snapshot corresponde a qué
  ejercicio, para tener trazabilidad del progreso del asistente.

---

## 8. Escalada de agresividad por fases

De menos a más invasivo. No pasar a la fase siguiente hasta que Jarvis maneje la
anterior de forma repetible.

### Fase 0 — Recon pasivo
Descubrimiento del /24, hosts vivos, puertos, versiones de servicio (nmap sin
scripts agresivos). **Criterio de avance:** Jarvis arma un inventario correcto del
range sin tocar el gate de scope indebidamente.

### Fase 1 — Escaneo activo
nmap con NSE, escaneo web con ZAP (spider + scan activo), enumeración de servicios.
**Criterio:** Jarvis identifica vulnerabilidades concretas y las mapea a CVEs/tools.

### Fase 2 — Explotación
Web (SQLMap en DVWA, retos de Juice Shop) y servicios (Metasploit en
Metasploitable, vulhub por CVE). **Criterio:** Jarvis obtiene shell/acceso de
forma reproducible en blancos suaves y medios.

### Fase 3 — RCE y post-explotación
EternalBlue/SMB en Windows viejo → Meterpreter; luego post-explotación (hashes,
migración, persistencia de laboratorio, pivote a otro blanco del range).
**Criterio:** Jarvis pasa de un acceso inicial a control total y se mueve dentro
del range.

### Fase 4 — Estrés / DoS (la más brutal, con más cuidado)
Floods, saturación de servicios, captura masiva — **solo** contra blancos del
range, **nunca** contra el host, WSL2 ni la LAN. **Criterio:** se prueba el
comportamiento de Jarvis bajo carga y su respeto al scope. Restaurar snapshots
después, sí o sí.

Regla transversal en todas las fases: **cada acción valida el target contra
`authorized_targets.yaml`**. Si Jarvis intenta algo fuera de `10.13.37.0/24`, la
tool debe negarse — y eso mismo es un test válido del gate.

---

## 9. Checklist de puesta en marcha

**A. Plataforma**
- [ ] Confirmar espacio libre en los 3 SSD (480 GB c/u; NVMe para activas, SATA para biblioteca — §4.4).
- [ ] Configurar VMware para guardar las VMs activas en el **M.2 NVMe** y la biblioteca/BASE en un **Kingston SATA**.
- [ ] Verificar que WSL2/Jarvis funciona (Hyper-V/WHP activo).
- [ ] Instalar **VMware Workstation Pro** (cuenta Broadcom gratis).
- [ ] Confirmar que VMware arranca una VM de prueba **con WSL2 encendido** (modo WHP OK).

**B. Red**
- [ ] Crear la red aislada del range (host-only / LAN segment, sin NAT), `10.13.37.0/24`.
- [ ] Verificar que el rango **no colisiona** con la LAN doméstica ni con la subred de WSL2.
- [ ] Confirmar que los blancos **no tienen** salida a internet ni a la LAN.

**C. Atacante**
- [ ] Crear VM **Kali** (2–4 vCPU, 4 GB, 40–80 GB) con eth0 en el range (.10).
- [ ] (Opcional) segunda placa NAT en Kali solo para actualizar, apagada en ataques.
- [ ] Snapshot `kali-BASE`.

**D. Blancos (de suave a brutal, incorporar por etapas)**
- [ ] Metasploitable 2 (.30) + snapshot `-BASE-limpio`.
- [ ] DVWA (.20) — contenedor o VM — + snapshot BASE.
- [ ] OWASP Juice Shop (.21) + snapshot BASE.
- [ ] (Medio) catálogo vulhub por CVE, según objetivos.
- [ ] (Fuerte) Windows 7/2008 SMBv1 (.40) + snapshot BASE.
- [ ] (Fuerte) Metasploitable 3 Windows + snapshot BASE.
- [ ] (Brutal) máquina(s) VulnHub OSCP-like + snapshot BASE.

**E. Jarvis**
- [ ] Agregar `10.13.37.0/24` a `backend/authorized_targets.yaml` **a mano**.
- [ ] Elegir la variante de conexión (recom.: Jarvis → Kali → blancos).
- [ ] Probar que una tool de pentest se **niega** contra una IP fuera del range (test del gate).
- [ ] Probar recon (Fase 0) contra el /24 y validar el inventario.

**F. Operación**
- [ ] Ejecutar el bucle atacar → romper → restaurar por fases (§8).
- [ ] Documentar cada ejercicio y su snapshot en una nota de Obsidian de Jarvis.
- [ ] No apilar dos blancos Windows pesados a la vez (§4).

---

## Fuentes (investigación 2026)

- [VirtualBox vs VMware Workstation in 2026 (guía práctica)](https://medium.com/@himadrisingh061/virtualbox-vs-vmware-workstation-in-2026-a-students-practical-guide-to-building-your-own-virtual-a67dc438639e)
- [VMware vs VirtualBox 2026: I/O gap, free tier](https://tech-insider.org/vmware-vs-virtualbox-2026/)
- [How To Set Up A Penetration Testing Lab (2026 Guide)](https://passitexams.com/articles/how-to-set-up-a-penetration-testing-lab/)
- [Home Pentest Lab Setup (Red Team Guide, 2026)](https://redteamguide.com/guides/home-pentest-lab-setup/)
- [VMware Workstation and Hyper-V on the Same PC (2026)](https://peoplearegeek.com/articles/vmware-hyper-v-coexistence/)
- [WSL2 needs Hyper-V — conflicto con 3rd party (microsoft/WSL #5030)](https://github.com/microsoft/WSL/issues/5030)
- [Nested Virtualization with Hyper-V and VMware (Microsoft Learn)](https://learn.microsoft.com/en-us/answers/questions/994875/nested-virtualization-with-hyper-v-and-vmware)
- [7 Vulnerable Applications for Practicing Pentesting](https://rafed.github.io/devra/posts/security/vulnerable-applications-for-practicing-pentesting/)
- [Build a Local Pentest Lab: Kali + Juice Shop + DVWA](https://medium.com/@divyanshusainialok/build-a-local-pentest-lab-in-20-minutes-attacker-kali-vulnerable-vm-owasp-juice-shop-dvwa-ed8a24f09ff0)
- [Metasploitable (SourceForge)](https://sourceforge.net/projects/metasploitable/)
- [VulnHub — Vulnerable By Design](https://www.vulnhub.com/)
- [MS17-010 EternalBlue module (metasploit-framework)](https://github.com/rapid7/metasploit-framework/blob/master/documentation/modules/exploit/windows/smb/ms17_010_eternalblue.md)
