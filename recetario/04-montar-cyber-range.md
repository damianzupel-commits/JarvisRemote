# 04 — Montar el cyber range

> Levantar un laboratorio de seguridad **aislado** (`10.13.37.0/24`, sin internet)
> con una máquina de ataque (Kali) y blancos vulnerables (Metasploitable, DVWA,
> Juice Shop) para practicar pentest y probar la detección de Raphael de forma
> contenida y legal.
>
> Basada en [`../lab/CYBER-RANGE-DESIGN.md`](../lab/CYBER-RANGE-DESIGN.md) (topología,
> blancos, snapshots) y [`../lab/RETOMAR-LAB.md`](../lab/RETOMAR-LAB.md) (dónde se
> quedó y los comandos listos para copiar).

## Qué produce

Una red interna aislada con Kali (atacante) y al menos un blanco, con snapshots
BASE limpios, verificada con `ping` + `nmap`. El range queda listo para las recetas
05 (estrés nocturno) y 06 (hardening).

## Estación / especialista

Seguridad / **Pentest** (el Salsero de seguridad). **Requiere PC con admin**
(instalar VirtualBox/VMware, Docker con UAC). Varios pasos son manuales de Damian
(instaladores con UAC) — Raphael no puede.

## Ingredientes (requisitos previos)

- **VirtualBox 7.2.x** + Extension Pack (o VMware Workstation Pro, plan A del
  diseño). *Ya instalado en el estado de RETOMAR-LAB.*
- **Kali Linux 2026.2** y **Metasploitable 2** importadas. *Ya hecho.*
- **Red interna "labnet"** con servidor DHCP `10.13.37.100–200`, gateway `.1`.
  *Ya creado.*
- Para blancos web: **Docker Desktop** (usa el WSL2 que ya está) — **todavía no
  instalado**, lo instala Damian a mano (MSI + UAC).
- *(Opcional)* key de **Nessus Essentials** (registrarse en tenable.com, gratis
  hasta 16 IPs).

## Pasos

**Dónde quedó (2026-08-17):** plataforma y red del range listas; Metasploitable
booteando. Falta loguear, sacar IPs, encender Kali y verificar conectividad.

1. **Metasploitable — encender y sacar IP.** Login `msfadmin`/`msfadmin`, correr
   `ifconfig` (es viejo, no `ip a`), anotar la IP de `eth0` (rango .100–.200). Si
   no tomó, `sudo dhclient eth0`.

2. **Kali — encender y loguear.** Login `kali`/`kali`, verificar que `eth0`
   (labnet) tomó IP: `ip a`.

3. **Verificar conectividad Kali → blanco.** `ping -c 4 <ip_metasploitable>` y
   `nmap -sV <ip_metasploitable>` (debe mostrar muchos puertos: 21, 22, 23, 80,
   139/445, 3306, 5432, 8180…). Si responden, el range está vivo y aislado.

4. **Snapshot BASE "limpio" de cada VM, ANTES de atacar.** Convención del diseño:
   `metasploitable2-BASE-limpio`, `kali-BASE`. Por CLI:
   `VBoxManage snapshot "Metasploitable2" take "metasploitable2-BASE-limpio"`.
   Regla del "máx. 3": un BASE por blanco (sagrado); PRE/POST desechables, borralos
   al cerrar cada sesión.

5. **(Fase siguiente) Blancos web por Docker** (tras instalar Docker Desktop con
   "Use WSL 2 based engine"):

   ```powershell
   docker run --rm -it -p 8080:80 ghcr.io/digininja/dvwa:latest   # http://localhost:8080
   docker run --rm -p 3000:3000 bkimminich/juice-shop             # http://localhost:3000
   ```

   ⚠️ Por defecto corren en el **host**, no dentro de labnet → rompe el aislamiento
   estricto. Para rigor, correrlos dentro de una VM Linux en labnet y accederlos por
   su IP `10.13.37.x`.

6. **Autorizar el range en Raphael (a mano, gate de scope).** Agregar a
   `backend/authorized_targets.yaml` (ni Raphael ni las tools pueden escribirlo):

   ```yaml
   authorized:
     - cidr: 10.13.37.0/24
       label: "cyber-range-local"
       note: "Lab aislado, blancos propios."
   ```

## Tiempo estimado

Pasos 1–4: ~30–45 min. Sumar blancos web + Docker: otra sesión. Instaladores con
UAC dependen de Damian.

## Notas / errores comunes

- **VirtualBox no tiene auto-snapshots** (VMware sí): los BASE/PRE/POST se hacen a
  mano o scripteando `VBoxManage snapshot`.
- **IPs DHCP vs "fijas".** El diseño sugería `.10`/`.30` estáticas; con DHCP las VMs
  toman `.100–.200`. No es problema: el `/24` autorizado las cubre igual.
- **Aislamiento:** los blancos van con **una sola placa** en labnet (sin NAT). Kali
  puede tener NAT solo para `apt update`, pero **apagala durante los ataques**.
- Conexión recomendada: **Raphael → Kali → blancos** (Raphael orquesta, Kali lanza
  las tools pesadas dentro del segmento).

## ¿Candidata a skill?

**📝 receta a mano.** El montaje inicial es mayormente manual (instaladores con UAC,
import de VMs, snapshots en VirtualBox) y se hace una vez, no repetidamente. Lo que
sí puede vivir como automatización es el **arranque/verificación** del range ya
montado (encender VMs, chequear conectividad), pero el grueso queda humano.
