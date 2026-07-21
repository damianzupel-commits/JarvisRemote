# TLS para el backend (preparado, no activado)

Este directorio contiene (una vez que corras `generate_cert.sh`) `cert.pem` y
`key.pem` — un certificado self-signed para que el backend pueda servir
`https://`/`wss://` en vez de `http://`/`ws://` en texto plano.

**Estado actual: preparado pero apagado.** `TLS_ENABLED` en `backend/.env` está
en `false` por default (ver `app/config.py`) — la app del celular sigue
usando `ws://` normalmente, sin ningún cambio, hasta que se active a propósito.

## Por qué no está activado ya

Activar esto **corta la conexión actual del celular** hasta que se actualice
la URL guardada en la app (de `http://...` a `https://...`), y además un
certificado self-signed no es de confianza para Android/OkHttp por default —
hay que agregarlo a un Network Security Config en la app (o instalarlo como CA
de confianza en el celular) antes de que la conexión HTTPS funcione ahí. Si se
activa el flag en el backend sin haber hecho ese trabajo del lado de Android
primero, la app deja de poder conectar (fallo de validación de certificado) y
no hay forma de revertirlo remotamente si la única conexión que tenía el
usuario para acceder a la PC era justamente esta.

**Por eso esto se dejó listo pero no se activa solo — necesita a alguien
presente (físicamente en la PC, o con otra vía de acceso de respaldo) para
coordinar el corte.**

## Cómo activar cuando estés listo (con el usuario presente)

1. Generar el certificado si no existe todavía o si venció/cambiaron las IPs:
   ```bash
   cd backend/certs
   ./generate_cert.sh
   ```
2. En `backend/.env`, poner `TLS_ENABLED=true`.
3. **Lado Android — antes de reiniciar el backend**: agregar un Network
   Security Config a la app que confíe en este certificado específico (o en
   cualquier CA cuyo `subjectAltName` matchee), y recompilar/reinstalar el
   APK. Sin esto, la app no va a poder validar la conexión HTTPS y quedará
   sin acceso hasta revertir `TLS_ENABLED` a `false`.
4. Reiniciar el backend (`tray-app` o `python run.py`).
5. En la app → Ajustes, cambiar la URL del backend de `http://` a `https://`
   (mismo host/puerto) y guardar.
6. Confirmar que reconecta (REST y WebSocket) antes de dar por terminado el
   cambio.

## Regenerar el certificado

Corré `./generate_cert.sh` de nuevo si:
- Cambió la IP de Tailscale o la de LAN de la PC (están hardcodeadas como
  Subject Alternative Names en el script — actualizalas ahí primero).
- El certificado venció (dura 10 años desde que se generó).

`cert.pem`/`key.pem` nunca se commitean (ver `.gitignore`): no hace falta
versionarlos, se regeneran con el script.
