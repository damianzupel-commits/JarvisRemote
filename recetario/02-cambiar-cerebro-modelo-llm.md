# 02 — Cambiar el cerebro de Raphael (modelo LLM)

> Cambiar el modelo LLM que piensa y ejecuta en Raphael — pasar de Ollama local a
> un modelo cloud (DeepSeek V4 vía OpenRouter), o entre modelos. El cerebro es
> **uno solo**, definido por config; cambiarlo es editar tres renglones y probar.
>
> Basada en [`../vision/CONFIG-MODELO-OPENROUTER.md`](../vision/CONFIG-MODELO-OPENROUTER.md).

## Qué produce

Raphael respondiendo con el modelo elegido. Al terminar, un `curl` al endpoint de
chat devuelve una respuesta generada por el nuevo cerebro.

## Estación / especialista

Config/Modelo — **el Dueño (Damian) + el Jefe de cocina**. **Requiere PC.** Toca
`backend/.env` (privado, con secretos) → no se commitea.

## Ingredientes (requisitos previos)

- Cuenta en **OpenRouter** con una **API key** (https://openrouter.ai/keys) y
  **crédito cargado** (https://openrouter.ai/credits) — DeepSeek V4 es pago. Para
  validar sin gastar, alcanza un modelo con sufijo `:free`.
- El **parche de código de 2 líneas** aplicado (ver paso 1): hoy la API key del LLM
  está **hardcodeada** en `backend/app/llm_client.py` como `"lm-studio"`. Local
  funciona porque Ollama/LM Studio no la validan; **OpenRouter sí** → sin el parche,
  rechaza todo con `401`.
- Acceso a editar `backend/.env`.

## Pasos

1. **Aplicar el parche de la API key (una vez, requiere OK de Damian).** En
   `backend/app/config.py`, al lado de `lmstudio_base_url`, agregar:

   ```python
   llm_api_key: str = os.getenv("LLM_API_KEY", "lm-studio")
   ```

   Y en `backend/app/llm_client.py`, reemplazar la línea hardcodeada `api_key="lm-studio"`
   por `api_key=settings.llm_api_key`. El default local sigue idéntico; cero impacto
   en modo local.

2. **Cargar crédito** en OpenRouter (o elegir un `:free` para validar la conexión
   primero).

3. **Editar los 3 renglones de `backend/.env`** (poné tu key real):

   ```dotenv
   LMSTUDIO_BASE_URL=https://openrouter.ai/api/v1
   LMSTUDIO_MODEL=deepseek/deepseek-v4-pro-0813
   LLM_API_KEY=sk-or-v1-TU_KEY_ACA
   ```

   Para el modelo barato de ruteo: `LMSTUDIO_MODEL=deepseek/deepseek-v4-flash-0731`.
   Para volver a local: `LMSTUDIO_BASE_URL=http://127.0.0.1:11434/v1` +
   `LMSTUDIO_MODEL=jarvis-text-v2` (o usar el selector Lite/Medio/Hard de la tray).

4. **Reiniciar el backend** (`cd backend && python run.py`).

5. **Probar** contra el endpoint de chat de Raphael (reemplazá `TU_API_KEY` por el
   `API_KEY` **del backend**, NO la de OpenRouter):

   ```bash
   curl -X POST http://localhost:8000/api/chat \
     -H "Authorization: Bearer TU_API_KEY" -H "Content-Type: application/json" \
     -d "{\"message\": \"Decime en una línea qué modelo sos.\"}"
   ```

6. *(Opcional, recomendado con cloud)* `LLM_RETRY_ON_TIMEOUT=true` en `.env` para
   reintentar ante caídas transitorias de red.

## Tiempo estimado

10–20 minutos si el parche ya está y hay crédito. La primera vez, sumar el alta de
cuenta/crédito en OpenRouter.

## Notas / errores comunes

- El nombre `LMSTUDIO_*` es **legacy**: hoy apunta a Ollama (11434) o a OpenRouter,
  no a LM Studio. Son las variables correctas para el LLM de chat pese al nombre.
- **`API_KEY` ≠ `LLM_API_KEY`.** `API_KEY` es el token que el celular/cliente le
  manda al backend. `LLM_API_KEY` es la key del proveedor LLM. No las confundas.
- `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` son un servidor aparte (LM Studio real,
  puerto 1234, embeddings del vault): **no se tocan**, siguen locales.
- Errores típicos: `401` = key mal/no seteada (revisá el parche del paso 1); `402`
  o mensaje de saldo = falta crédito; `404 model not found` = slug mal escrito.
- Ojo con `MODEL_CONTEXT_TOKENS` (config.py, hoy 32768): DeepSeek V4 admite 1M+;
  dejalo o subilo según lo que le mandes.

## ¿Candidata a skill?

**📝 receta a mano.** Se hace poco (cambiar de cerebro no es diario) y varios pasos
son de criterio/humano: aplicar el parche con OK, cargar crédito, elegir el modelo.
No justifica automatizar hoy. Cuando el cambio de modelo se vuelva rutinario (router
de modelos del blueprint), migra ahí.
