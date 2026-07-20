from openai import OpenAI

from .config import settings

# LM Studio expone una API compatible con OpenAI en local; no valida la api_key,
# pero el SDK exige que mandemos algo.
client = OpenAI(base_url=settings.lmstudio_base_url, api_key="lm-studio")
