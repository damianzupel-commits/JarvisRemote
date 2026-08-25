# Co-host de stream — MVP (prueba técnica mínima)

Prueba de concepto **sin personalidad, sin voz, sin OBS**. Solo comprueba que el
circuito funciona: captura la pantalla → la manda a un modelo de **visión** vía
OpenRouter → imprime por consola lo que el modelo comenta.

## Pasos para correrlo

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Copiar el ejemplo de config y poner tu key real
copy .env.example .env
#   (en Linux/Mac: cp .env.example .env)
#   Editá .env y reemplazá OPENROUTER_API_KEY con tu key de openrouter.ai

# 3. Correr
python main.py
```

Corta con `Ctrl+C`.

## Notas importantes

- **La key va SIEMPRE en el `.env`, nunca en el código.** El `.env` no se
  commitea (ya está cubierto por `.gitignore`). Solo se versiona `.env.example`
  con placeholders.
- **El modelo TIENE que ser de visión (multimodal).** El default es
  `google/gemini-flash-1.5`. Si ese slug no existe o no acepta imágenes,
  alternativas de visión en OpenRouter:
  - `qwen/qwen-2-vl-7b-instruct`
  - `deepseek/deepseek-v4-flash-vision-exp`
  - o cualquier otro con visión de https://openrouter.ai/models
  Confirmá el slug exacto ahí y ponelo en `VISION_MODEL` dentro del `.env`.
- Ajustá `CAPTURE_INTERVAL_SECONDS` en el `.env` para cambiar cada cuántos
  segundos captura.
- La captura se reduce a ~1024px de ancho antes de mandarla para bajar costo.
