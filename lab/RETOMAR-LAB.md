# RETOMAR-LAB.md — Guía para retomar el armado del cyber range aislado

> Guía de continuación (no ejecutable). Escrita el 2026-08-17 para que Damian
> retome el armado del laboratorio sin perder el hilo cuando vuelva a la PC.
> Alinea con `lab/CYBER-RANGE-DESIGN.md` (topología, blancos, snapshots) y
> `lab/DETECCION-ESTRES-NOCTURNO.md` (bucle de detección/emulación). **No instala
> ni ejecuta nada**: es el plano del próximo tramo.

---

## 1. Dónde quedamos (estado actual, 2026-08-17)

Ya está hecho **el arranque de la plataforma y la red del range**:

- **VirtualBox 7.2.14** instalado en Windows + **Extension Pack**.
  - Nota de alineación con el diseño: `CYBER-RANGE-DESIGN.md` recomendaba VMware
    Workstation Pro y dejaba **VirtualBox como plan B** (§2.3). Damian fue con el
    plan B — perfectamente válido. La única diferencia práctica: VirtualBox **no
    tiene auto-snapshots** integrados, así que los snapshots BASE/PRE/POST se
    hacen a mano (o scripteando `VBoxManage snapshot`). Todo lo demás del diseño
    aplica igual.
- **Kali Linux 2026.2** importada (imagen prearmada), con:
  - **Adaptador 1 = Red interna "labnet"** → la placa de ataque, aislada (eth0).
  - **Adaptador 2 = NAT** → solo para `apt update` de Kali (eth1). **Apagala
    durante los ataques** (§3.3 del diseño: los blancos nunca ven internet, Kali
    sí pero solo para actualizar).
- **Metasploitable 2** creada como VM nueva con el disco `Metasploitable.vmdk`
  enganchado, **Adaptador 1 = Red interna "labnet"** (sin NAT, totalmente
  aislada). Correcto: los blancos van con **una sola placa** en labnet.
- **Servidor DHCP en la red interna labnet** creado con `VBoxManage dhcpserver add`:
  - Rango **10.13.37.100 – 10.13.37.200**
  - server-ip **10.13.37.1**, máscara **255.255.255.0**
  - Coincide con el `10.13.37.0/24` del diseño (§3.2). El `.1` es el gateway
    ficticio (sin ruta a internet), tal cual el diseño.

**Dónde se cortó:** Metasploitable estaba booteando. Falta loguear, sacar su IP,
encender Kali y verificar conectividad entre ambas.

> ⚠️ **Detalle de IPs — DHCP vs las IPs "fijas" del diseño.** El diseño sugería
> IPs estáticas (Kali `.10`, Metasploitable `.30`). Con el DHCP que armaste, las
> VMs van a tomar IPs **dinámicas en el rango .100–.200**, no las .10/.30. **No es
> un problema**: `authorized_targets.yaml` autoriza todo el `/24`, así que Jarvis
> las alcanza igual. Si más adelante querés que coincidan con la convención del
> diseño (útil para que los nombres de snapshot y las notas sean predecibles),
> podés o bien fijar IPs estáticas dentro de cada VM, o reservar direcciones por
> MAC en el DHCP. Opcional; para arrancar, DHCP dinámico alcanza.

---

## 2. Próximos pasos inmediatos (checklist en orden)

- [ ] **a. Metasploitable — encender y sacar IP.**
  - Encender la VM (ya estaba booteando).
  - Login: usuario `msfadmin` / contraseña `msfadmin`.
  - Correr `ifconfig` (Metasploitable 2 es viejo: usa `ifconfig`, no `ip a`).
  - **Anotar la IP de `eth0`** — debería ser `10.13.37.1xx` (rango DHCP .100–.200).
    Si `eth0` no tomó IP, forzá con `sudo dhclient eth0`.
- [ ] **b. Kali — encender y loguear.**
  - Login: usuario `kali` / contraseña `kali`.
  - Verificar que `eth0` (labnet) tomó IP del rango: `ip a` o `ifconfig eth0`.
    Debería estar también en `10.13.37.1xx`.
- [ ] **c. Verificar conectividad Kali → blanco.**
  - `ping -c 4 <ip_metasploitable>` (la que anotaste en el paso a).
  - Escaneo de prueba: `nmap -sV <ip_metasploitable>`
    (Metasploitable 2 tiene que mostrar un montón de puertos: 21 vsftpd, 22 ssh,
    23 telnet, 80, 139/445 Samba, 3306 MySQL, 5432 Postgres, 8180 Tomcat, etc.).
  - Si el ping y el nmap responden, el range está vivo y aislado.
- [ ] **d. Snapshot BASE "limpio" de cada VM — ANTES de atacar.**
  - Convención del diseño (§7.1): nombre `<blanco>-BASE-limpio`.
  - En VirtualBox: VM apagada o corriendo → *Máquina → Tomar instantánea*.
    - Metasploitable → `metasploitable2-BASE-limpio`
    - Kali → `kali-BASE`
  - Por CLI (equivalente): `VBoxManage snapshot "Metasploitable2" take "metasploitable2-BASE-limpio"`
  - Recordá la **regla del "máx. 3"** (§4.5): un BASE por blanco, sagrado; los
    PRE/POST son desechables, revertí y borralos al terminar cada sesión.

Cuando termines a–d, el range base está listo y podés empezar a sumar blancos web
(fase siguiente) y a correr la Fase 0 (recon) del diseño.

---

## 3. Fase siguiente — comandos listos para copiar/pegar

### 3.1 Docker Desktop en Windows (prerrequisito de DVWA / Juice Shop / Caldera)

Docker **todavía no está instalado** (confirmado en `ESTADO.md`). WSL2 ya lo
tenés, que es el prerrequisito. Falta el instalador (MSI + UAC, lo hace Damian a
mano — Jarvis no puede).

- Descarga oficial: **https://www.docker.com/products/docker-desktop/**
- Al instalar, dejar marcado **"Use WSL 2 based engine"** (usa el WSL2 que ya
  tenés, no la VM Hyper-V vieja). Reiniciar si lo pide.
- Verificar en una terminal: `docker run --rm hello-world`

> Nota de arquitectura: instalar Docker Desktop también destraba la propuesta de
> sandboxing en contenedor de `pc_run_command`/`browser` (ver `ESTADO.md`). Son
> dos usos distintos del mismo Docker; tenerlo sirve para ambos.

### 3.2 DVWA por Docker

```powershell
docker run --rm -it -p 8080:80 ghcr.io/digininja/dvwa:latest
```

→ Abrir **http://localhost:8080** (login por defecto `admin` / `password`, y
"Create / Reset Database" en el primer arranque).

> ⚠️ **Dónde queda accesible.** Este contenedor corre en el **host Windows** y se
> publica en `localhost:8080` **del host** — es decir, DVWA queda accesible desde
> tu PC, **no desde dentro de la red labnet**. Para probar rápido desde el
> navegador del host o desde Jarvis-en-WSL2 está perfecto. **Pero rompe el
> aislamiento estricto del diseño** (§3), que quiere todos los blancos dentro de
> `10.13.37.0/24` sin ruta al host/LAN.
>
> **Opción para aislamiento total** (recomendada por el diseño §4.3): correr DVWA
> como contenedor **dentro de una VM Linux liviana conectada a labnet** (o dentro
> de la propia Kali/un target Linux con placa en labnet), y publicarlo en la IP
> `10.13.37.x` de esa VM. Así el blanco vive en el segmento aislado y Jarvis lo
> ataca por su IP del range, igual que a Metasploitable. Para empezar podés usar
> la versión en el host; cuando quieras rigor de aislamiento, movelo adentro de
> labnet.

### 3.3 OWASP Juice Shop por Docker

```powershell
docker run --rm -p 3000:3000 bkimminich/juice-shop
```

→ Abrir **http://localhost:3000**. Aplica la **misma nota de aislamiento** que
DVWA: por defecto queda en el host; para aislamiento total, correlo dentro de una
VM en labnet y accedé por su IP `10.13.37.x`.

### 3.4 Atomic Red Team (dentro de la VM blanco Windows — NO en el host)

Emulación de técnicas atómicas ATT&CK para la prueba de detección
(`DETECCION-ESTRES-NOCTURNO.md`). Se instala **dentro del blanco Windows**, no en
el host ni en Kali. Comandos oficiales vigentes de Red Canary (verificados
2026-08-17):

Instalar el framework de ejecución (`Invoke-AtomicRedTeam`):

```powershell
IEX (IWR 'https://raw.githubusercontent.com/redcanaryco/invoke-atomicredteam/master/install-atomicredteam.ps1' -UseBasicParsing); Install-AtomicRedTeam
```

Si PowerShell se queja de que los scripts están deshabilitados, reabrí la consola
con `powershell -exec bypass` y repetí.

Para además bajar la carpeta de **atomics** (los tests; el instalador NO la baja
por defecto porque muchos disparan el antivirus — esto es lo que querés medir):

```powershell
Install-AtomicRedTeam -getAtomics
```

Alternativa vía PowerShell Gallery (equivalente):

```powershell
Install-Module -Name invoke-atomicredteam, powershell-yaml -Scope CurrentUser
```

Correr un test (ejemplo — PowerShell de T1059.001), con setup y cleanup:

```powershell
Import-Module invoke-atomicredteam -Force
Invoke-AtomicTest T1059.001 -GetPrereqs
Invoke-AtomicTest T1059.001
Invoke-AtomicTest T1059.001 -Cleanup
```

### 3.5 MITRE Caldera (servidor de emulación multi-paso)

Para las operaciones encadenadas / C2 de laboratorio que Atomic no cubre. El
diseño apunta a **Caldera v5**. Comandos oficiales vigentes (verificados
2026-08-17). Cloná **siempre una release en formato `x.x.x`**, no `master`
(clonar master puede traer bugs, dice la doc oficial):

**Opción A — Docker (más simple si ya instalaste Docker Desktop):**

```bash
git clone https://github.com/mitre/caldera.git --recursive --branch 5.3.0
cd caldera
docker build --build-arg WIN_BUILD=true . -t caldera:server
docker run -p 7010:7010 -p 7011:7011/udp -p 7012:7012 -p 8888:8888 caldera:server
```

**Opción B — Python (sin Docker):** requiere Python 3.9+, Node y Go instalados.

```bash
git clone https://github.com/mitre/caldera.git --recursive --branch 5.3.0
cd caldera
pip3 install -r requirements.txt
python3 server.py --insecure --build
```

→ UI en **http://localhost:8888** (usuario/clave por defecto en `conf/default.yml`,
p. ej. `red` / contraseña generada; revisá el yml). El **agente Sandcat** se
despliega **dentro del blanco** en labnet y reporta al servidor Caldera en la IP
del range (`10.13.37.10` según el diseño, o la IP DHCP que tome el colector).
Mantené todo el C2 **dentro de labnet**, nunca hacia afuera.

> Verificá la última release estable en https://github.com/mitre/caldera/releases
> por si `5.3.0` ya quedó atrás cuando retomes; cambiá el `--branch` en
> consecuencia.

---

## 4. Integración con Jarvis

- **Antes de que Jarvis toque un solo blanco**, agregá el rango del lab a
  `backend/authorized_targets.yaml` **a mano** (ni Jarvis ni las tools pueden
  escribir ese archivo — es el gate de scope). Ya está previsto en el diseño (§6.2):

  ```yaml
  authorized:
    - cidr: 10.13.37.0/24
      label: "cyber-range-local"
      note: "Lab aislado, blancos propios. Alta 2026-08-17."
  ```

  Con el `/24` autorizado cubrís tanto las IPs DHCP (.100–.200) como las .10/.30
  del diseño si algún día fijás estáticas.

- **Todo el pentest y la prueba de estrés corren SOLO dentro de labnet
  (`10.13.37.0/24`).** Cualquier tool de pentest activo de Jarvis valida el target
  contra `authorized_targets.yaml` y se **niega** fuera del range. Probar esa
  negativa contra una IP externa es, en sí, un test válido del gate (diseño §8).

- Conexión recomendada (diseño §6.1): **Jarvis → Kali → blancos** (Jarvis
  orquesta, Kali lanza las tools pesadas dentro del segmento). Mantiene el tráfico
  ofensivo naciendo dentro de labnet.

---

## 5. Pendiente de Damian desde el celular

- [ ] **Registrarse en https://www.tenable.com/** para obtener la **key de Nessus
  Essentials** (escáner de vulnerabilidades gratuito para uso personal, hasta 16
  IPs — alcanza de sobra para el range). Se puede hacer desde el celular mientras
  no estás en la PC; la key llega por mail y la activás cuando instales Nessus en
  el lab.

---

## 6. Pendiente en la PC — pipeline de ingesta de YouTube

- [ ] **Correr el pipeline de ingesta de YouTube recién construido** para procesar
  los videos nuevos de la playlist. Va **en la PC** porque necesita el **modelo de
  Jarvis levantado** y **acceso a YouTube**.
  - Módulo: `backend/app/ingestion/youtube_playlist.py`. También expuesto como
    **tool del agente**: `youtube_ingest_playlist`.
  - Prueba con un solo video (recomendado la primera vez):

    ```bash
    cd backend
    python -m app.ingestion.youtube_playlist --max-videos 1
    ```

  - Procesar todos los videos nuevos (sin el flag):

    ```bash
    cd backend
    python -m app.ingestion.youtube_playlist
    ```

  - ⚠️ **Todavía NO fue probado contra YouTube real.** La primera corrida, además
    de ingerir el video, **valida el pipeline** de punta a punta — por eso arrancá
    con `--max-videos 1` y revisá el resultado antes de largar la corrida completa.

---

## Fuentes (verificación 2026-08-17)

- [Installing Invoke-AtomicRedTeam — Red Canary (wiki oficial)](https://github.com/redcanaryco/invoke-atomicredteam/wiki/Installing-Invoke-AtomicRedTeam)
- [redcanaryco/invoke-atomicredteam (repo oficial)](https://github.com/redcanaryco/invoke-atomicredteam)
- [Installing Caldera — documentación oficial](https://caldera.readthedocs.io/en/latest/Installing-Caldera.html)
- [mitre/caldera (repo oficial)](https://github.com/mitre/caldera/)
- [Docker Desktop (descarga oficial)](https://www.docker.com/products/docker-desktop/)
- [Nessus Essentials (Tenable)](https://www.tenable.com/products/nessus/nessus-essentials)
