from openai import AsyncOpenAI

from .config import settings

# LM Studio expone una API compatible con OpenAI en local; no valida la api_key,
# pero el SDK exige que mandemos algo.
#
# Cliente async: el servidor corre en un solo event loop (uvicorn), y una
# inferencia local puede tardar decenas de segundos. Con el cliente
# sincrónico, esa llamada bloquea el loop entero mientras "piensa" — nada
# más puede procesarse en el medio, ni /api/health ni los frames del
# WebSocket del celular (eso rompía la conexión del celular en cada tool
# call: el WS quedaba sin atender justo cuando más se lo necesitaba).
client = AsyncOpenAI(base_url=settings.lmstudio_base_url, api_key="lm-studio")
