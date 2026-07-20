# tray-app (placeholder — próximo paso)

Tray app de Windows que administra el `backend`: lo arranca como subproceso, lo
para, y muestra su estado (corriendo / caído, IP de Tailscale, últimos logs) desde
el ícono en la bandeja del sistema.

## Decisión técnica

**Python + [pystray](https://github.com/moses-palmer/pystray) + Pillow** para el
ícono. Mismo lenguaje que el backend (no hace falta un segundo runtime como
Electron o .NET), y es lo mínimo necesario para un tray icon con menú en Windows.

## Plan (no implementado todavía)

```
tray-app/
  requirements.txt      # pystray, pillow
  tray.py                # ícono + menú (Start/Stop backend, Abrir logs, Salir)
  icon.png                # ícono de la bandeja
```

- `tray.py` lanza `python ../backend/run.py` como subprocess al iniciar (o al
  hacer click en "Start"), y lo mata con `Stop`.
- El menú muestra estado (poll a `GET /api/health` cada pocos segundos) y la IP
  de Tailscale detectada (`tailscale ip -4`).
- Opcional más adelante: registrar el tray app para que arranque con Windows
  (carpeta de Startup o Tarea Programada).

Se scaffoldea en un paso siguiente, una vez que el backend esté probado end to
end contra LM Studio.
