# 08 — Shell del celular por SSH + Tailscale

> Tener la terminal de la PC en el bolsillo: conectarse por **SSH desde el celular**
> a la PC Windows, de forma segura, **solo sobre la red privada de Tailscale**
> (nunca exponiendo el puerto a internet). Receta **nueva** — no hay doc de diseño
> previo; corresponde a la comanda "SSH desde el celular" de
> [`../COMANDAS.md`](../COMANDAS.md).

## Qué produce

Una sesión SSH funcionando desde el celular (con Termius) contra la PC, por la IP
de Tailscale `100.x.x.x`. Desde el celu se puede correr comandos en la PC como si
estuvieras sentado frente a ella.

## Estación / especialista

Sistema / **Red** (el de la línea caliente). **Requiere PC con admin** (habilitar
OpenSSH Server es una operación administrativa).

## Ingredientes (requisitos previos)

- Windows 10/11 con **PowerShell como administrador**.
- **Tailscale** instalado y logueado en **la PC y el celular**, ambos en la misma
  tailnet.
- **Termius** (u otro cliente SSH) instalado en el celular.
- El **nombre de usuario de Windows** y su contraseña (para autenticar el login SSH).

## Pasos

1. **Habilitar el OpenSSH Server en Windows** (PowerShell como admin):

   ```powershell
   Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
   ```

2. **Arrancar el servicio y dejarlo automático** (para que sobreviva reinicios):

   ```powershell
   Start-Service sshd
   Set-Service -Name sshd -StartupType Automatic
   ```

3. **Sacar la IP de Tailscale de la PC:**

   ```powershell
   tailscale ip -4
   ```

   Devuelve una `100.x.x.x` — esa es la dirección a la que se conecta el celular.

4. **Conectar desde el celular con Termius:**
   - **Host:** la IP `100.x.x.x` del paso 3.
   - **Usuario:** tu usuario de Windows.
   - **Puerto:** `22`.
   - Contraseña: la de tu cuenta de Windows.

## Tiempo estimado

10–15 minutos la primera vez (asumiendo Tailscale ya instalado en ambos).

## Notas / errores comunes

- **🔒 Seguridad, no negociable: solo sobre Tailscale. NUNCA abrir el puerto 22 a
  internet** ni hacer port-forwarding en el router. Tailscale ya da una red privada
  cifrada entre tus dispositivos; exponer el 22 público te llena de intentos de
  fuerza bruta en minutos.
- Si el login falla, revisar que el servicio `sshd` esté corriendo
  (`Get-Service sshd`) y que el firewall de Windows permita OpenSSH Server (la
  instalación suele crear la regla; si no, habilitarla a mano).
- Verificá que ambos dispositivos aparezcan **online en la misma tailnet** antes de
  intentar conectar.
- *(Endurecimiento opcional)* pasar de contraseña a **clave pública** y deshabilitar
  el login por password en `sshd_config` — más seguro para uso habitual.

## ¿Candidata a skill?

**📝 receta a mano.** Es un setup que se hace **una sola vez** por máquina; después
la conexión ya queda. No hay nada repetitivo que automatizar. Queda como receta de
referencia para cuando se configure una PC nueva.
