# Configuración: apuntar Jarvis a DeepSeek V4 vía OpenRouter

> Escrito el 2026-08-23. Objetivo: dejar el backend de Jarvis usando **DeepSeek V4**
> servido por **OpenRouter** (API por token, endpoint compatible con OpenAI), en
> lugar de Ollama/LM Studio local.
>
> **IMPORTANTE:** este doc es análisis + guía. **No** se tocó `backend/.env` (privado,
> tiene secretos), no se commiteó ni pusheó nada. Hay **un cambio de código mínimo
> pendiente** (ver sección 4) que NO se aplicó: sin él, OpenRouter va a rechazar los
> requests por falta de API key real.

---

## 1. Nombres de variable REALES que usa Jarvis (confirmados en el código)

Confirmado leyendo `backend/app/config.py` y `backend/app/llm_client.py`:

| Qué configura | Variable de entorno | Setting en código | Default |
|---|---|---|---|
| **base_url / endpoint del LLM** | `LMSTUDIO_BASE_URL` | `settings.lmstudio_base_url` | `http://localhost:1234/v1` |
| **nombre del modelo** | `LMSTUDIO_MODEL` | `settings.lmstudio_model` | `local-model` |
| **API key del proveedor LLM** | *(no existe hoy)* | **hardcodeada** `api_key="lm-studio"` en `llm_client.py` | — |

Notas clave:

- El nombre `LMSTUDIO_*` es **legacy** de una migración vieja desde LM Studio. Hoy en
  esta PC esas variables en realidad apuntan a **Ollama** (`http://127.0.0.1:11434/v1`).
  El nombre engaña, pero **son las variables correctas** para el LLM de chat/agente.
- `API_KEY` (en `config.py` línea 49 y en `.env`) **NO es** la key del proveedor LLM.
  Es el token que el **celular / cliente** manda al backend de Jarvis en el header
  `Authorization: Bearer <API_KEY>`. No la toques para esto.
- El cliente es `AsyncOpenAI` (SDK oficial de OpenAI), instanciado en
  `backend/app/llm_client.py`. **Es 100% compatible con OpenRouter** apuntando
  `base_url` a `https://openrouter.ai/api/v1` — OpenRouter expone exactamente el
  mismo protocolo OpenAI. El único bloqueante es la API key (ver sección 4).
- `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` son un servidor **aparte** (LM Studio real,
  puerto 1234, para embeddings del vault). **No se tocan** — seguirían siendo locales.

---

## 2. Slugs de modelo en OpenRouter

Verificado contra `openrouter.ai/deepseek` el 2026-08-23.

**Modelo potente (DeepSeek V4 — para la auditoría / agente principal):**

```
deepseek/deepseek-v4-pro-0813
```

Es la release GA de DeepSeek V4 Pro (MoE grande, contexto 1.05M). Precio de referencia:
~$0.66/M tokens input, ~$1.98/M output. (Alternativa más vieja: `deepseek/deepseek-v4-pro`,
la 0423.)

**Modelo barato (para ruteo / tareas simples):**

```
deepseek/deepseek-v4-flash-0731
```

DeepSeek V4 Flash (MoE, 13B activos de 284B, GA, contexto 1.31M, pensado para coding /
agentes). Precio de referencia: ~$0.04/M input, ~$0.13/M output — más de 10x más barato
que Pro. (Alias siempre-al-último: `deepseek/deepseek-v4-flash-latest`.)

> Confirmá los slugs exactos en https://openrouter.ai/models buscando "DeepSeek V4"
> antes de fijarlos: OpenRouter agrega/renombra revisiones seguido (fechas 0423 / 0731 /
> 0813, etc.).

---

## 3. Los renglones EXACTOS para `backend/.env`

Cambiar estas líneas en `backend/.env` (la key va con **placeholder** — poné la tuya real,
la sacás de https://openrouter.ai/keys):

```dotenv
LMSTUDIO_BASE_URL=https://openrouter.ai/api/v1
LMSTUDIO_MODEL=deepseek/deepseek-v4-pro-0813
LLM_API_KEY=sk-or-v1-TU_KEY_ACA
```

- `LMSTUDIO_MODEL` = slug potente. Para el modelo barato de ruteo, poné en su lugar
  `deepseek/deepseek-v4-flash-0731`.
- `LLM_API_KEY` es una variable **nueva** que hoy el código todavía no lee (ver sección 4).
  Sin el parche de la sección 4, esta línea no tiene efecto y OpenRouter devuelve
  `401 No auth credentials found`.

> **Recordá:** DeepSeek V4 es **pago**. Necesitás **crédito cargado** en OpenRouter
> (https://openrouter.ai/credits) o los requests fallan con error de saldo/límite.

### Validar la conexión SIN gastar crédito (opcional)

OpenRouter tiene modelos con sufijo `:free` (rate-limitado) para probar la conexión
antes de cargar plata. Poné temporalmente:

```dotenv
LMSTUDIO_MODEL=deepseek/deepseek-r1:free
```

y confirmá que responde. Verificá qué `:free` están disponibles hoy en
https://openrouter.ai/models?q=free (la oferta gratis rota). Una vez validada la
conexión, volvé al slug pago de V4.

---

## 4. Cambio de código necesario (NO aplicado)

**Hay un bloqueante:** la API key del LLM está **hardcodeada** en
`backend/app/llm_client.py`:

```python
client = AsyncOpenAI(
    base_url=settings.lmstudio_base_url,
    api_key="lm-studio",          # <-- hardcodeado; Ollama/LM Studio local lo ignoran
    timeout=settings.llm_request_timeout_seconds,
    max_retries=0,
)
```

Local funciona porque Ollama/LM Studio **no validan** la key. OpenRouter **sí la valida**,
así que con `"lm-studio"` va a rechazar todo. Parche mínimo (2 líneas), **pendiente de tu OK**:

**a)** En `backend/app/config.py`, al lado de `lmstudio_base_url` (línea ~52), agregar:

```python
    # API key del proveedor LLM. Vacío/ausente = "lm-studio" (Ollama/LM Studio local
    # la ignoran). Para OpenRouter u otro proveedor cloud, poné la key real acá.
    llm_api_key: str = os.getenv("LLM_API_KEY", "lm-studio")
```

**b)** En `backend/app/llm_client.py`, reemplazar la línea hardcodeada:

```python
    api_key=settings.llm_api_key,
```

Con ese cambio, el default local sigue idéntico (usa `"lm-studio"`) y OpenRouter toma la
key de `LLM_API_KEY`. Cero impacto en el modo local.

> Opcional pero recomendado con modelos cloud: prender el reintento ante timeout
> (`LLM_RETRY_ON_TIMEOUT=true` en `.env`) — ya existe en `config.py` (línea ~82) y está
> pensado justo para caídas transitorias de red contra un modelo remoto.

---

## 5. Cómo probar que quedó andando

Con el backend levantado (`cd backend && python run.py`), pegale al endpoint de chat de
Jarvis (reemplazá `TU_API_KEY` por el `API_KEY` **del backend**, no la de OpenRouter):

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer TU_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Decime en una línea qué modelo sos.\"}"
```

Si querés descartar Jarvis del medio y probar OpenRouter directo:

```bash
curl https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer sk-or-v1-TU_KEY_ACA" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"deepseek/deepseek-v4-pro-0813\", \"messages\": [{\"role\": \"user\", \"content\": \"ping\"}]}"
```

Errores típicos: `401` = key mal / no seteada (revisá la sección 4). `402` / mensaje de
saldo = falta crédito. `404 model not found` = slug mal escrito.

---

## 6. Checklist

- [ ] Cargar crédito en OpenRouter (o usar un `:free` para validar).
- [ ] Aplicar el parche de la sección 4 (2 líneas) — **requiere tu OK**.
- [ ] Editar las 3 líneas de `backend/.env` (sección 3) con la key real.
- [ ] Reiniciar el backend.
- [ ] Probar con el `curl` de la sección 5.
- [ ] (Opcional) `LLM_RETRY_ON_TIMEOUT=true` para el modo cloud.
- [ ] Ojo con `MODEL_CONTEXT_TOKENS` (config.py ~238): hoy 32768. DeepSeek V4 admite
      1M+, pero podés dejarlo o subirlo según lo que quieras mandarle.
