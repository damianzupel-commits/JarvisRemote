# installer

Instalador de un click del lado PC (backend + tray-app). Deja todo listo para
arrancar sin tener que instalar Ollama a mano, bajar modelos GGUF por tu cuenta,
ni escribir `backend/.env` a mano.

## Uso

Doble click en **`instalar.bat`** (esto es lo que hay que correr, un `.ps1` no
arranca solo con doble click en Windows). Alternativa desde una terminal:

```powershell
cd installer
.\Install-JarvisRemote.ps1
```

El wizard:

1. Detecta tu hardware (GPU/vendor/VRAM, RAM, disco libre) y recomienda un
   tier: **Lite** (Qwen3-8B), **Medio** (Qwen3-30B-A3B) o **Hard** (Medio +
   generación de video). Vos podés elegir cualquiera igual.
2. Instala Python venvs para `backend/` y `tray-app/` (pide confirmación antes
   de bajar Python si no lo tenés).
3. Verifica/instala Ollama, baja el modelo del tier elegido y lo deja con el
   alias que ya espera `tray-app/config.py` (`jarvis-text-lite` /
   `jarvis-text-v2` / `jarvis-text-hard`, vía `ollama cp`).
4. Escribe/actualiza `backend/.env` (API key, `FS_ALLOWED_ROOT`, y
   `LMSTUDIO_BASE_URL`/`LMSTUDIO_MODEL` apuntando al Ollama local — el nombre
   de esas variables quedó de la época de LM Studio, pero hoy el LLM real es
   Ollama, ver el comentario en el script). Nunca pisa una `API_KEY` que ya
   esté seteada.
5. Si detecta Tailscale, ofrece configurar `HOST` con tu IP de tailnet.

### Parámetros útiles

```powershell
.\Install-JarvisRemote.ps1 -Tier Lite              # sin preguntar, tier fijo
.\Install-JarvisRemote.ps1 -DryRun                 # simula todo, no toca nada
.\Install-JarvisRemote.ps1 -SkipOllama              # solo venvs + .env
.\Install-JarvisRemote.ps1 -SkipVenv                # solo Ollama + .env
.\Install-JarvisRemote.ps1 -IncludeDevDeps          # instala requirements-dev.txt (pytest, etc.)
```

`-DryRun` es la forma segura de revisar qué haría antes de correrlo en serio —
no descarga nada, no instala nada, no corre `ollama pull`.

## Qué NO hace (a propósito)

- **ComfyUI + Wan2.2 (tier Hard)**: no se automatiza. Son varios GB de pesos
  específicos (variante GGUF cuantizada) más, en GPUs AMD no soportadas
  oficialmente por ROCm, un venv de PyTorch aparte según la gfx exacta —
  automatizar esto a ciegas es más probable que rompa algo a que funcione. El
  wizard imprime una guía paso a paso al elegir Hard; el detalle completo está
  en `backend/README.md`.
- **Tailscale**: solo se detecta si ya está instalado (para sugerir `HOST`).
  Instalarlo requiere login interactivo con tu cuenta, no tiene sentido
  automatizarlo.
- **Android**: compilar/instalar la app y habilitar el Accessibility Service
  necesitan el celular físico conectado — ver `android-app/README.md` y
  `android-app/deploy.ps1`.
- **TLS**: preparado en el backend pero un cambio a propósito manual (corta el
  acceso hasta reconfigurar el lado Android) — ver `backend/certs/README.md`.

## Re-correrlo

Es seguro correrlo de nuevo (por ejemplo para cambiar de tier): no pisa una
`API_KEY` ya seteada, reusa los venvs si ya existen, y `ollama cp` es
idempotente. Cambiar de tier básicamente baja el modelo nuevo (si no lo tenías
ya) y actualiza `LMSTUDIO_MODEL` en `.env`.
