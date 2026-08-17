"""Tools `cloud_expert_code` y `cloud_expert_marketing` -- delegan a Gemini
Flash (Google AI Studio, free tier) un primer borrador de código o de texto
de marketing, agregado 2026-08-12.

Diseño acordado con Damian:
- `cloud_expert_code`: pensado específicamente para proyectos nuevos/no
  sensibles donde el modelo local viene inventando APIs (ej. el mod de
  Fabric -- ver app/tools/fabric_reference.py/opencode.py, el mismo problema
  de fondo). Jarvis se queda dueño de TODO el ciclo de calidad después: el
  borrador que devuelve esta tool es solo texto, sin efectos secundarios
  (no escribe archivos) -- el modelo que llamó a esta tool sigue siendo
  responsable de escribirlo (fs_write_file/code_apply_fix), auditarlo
  (security_scan_project) y testearlo (code_run_tests/
  security_audit_find_fix_verify) con las tools que ya existen. Esta tool
  NUNCA reemplaza ese ciclo, solo mejora el punto de partida.
- `cloud_expert_marketing`: mismo proveedor, para redactar contenido real
  (posts, README, guiones, textos de posicionamiento). Combinable con
  generate_image (ya existente) para separar quién escribe el copy de quién
  genera la imagen.

Gate de sensibilidad: NINGUNA de las dos manda nada a la nube sin que quien
llama pase `confirm_non_sensitive=true` explícitamente -- mismo criterio que
`confirm=true` en code_apply_fix o el whitelist de nmap_scan: una decisión
explícita en cada llamada, nunca un default que mande datos afuera solo por
no acordarse de pasar un flag. El texto de la tarea (`task`) es lo único que
sale de la máquina -- ninguna de las dos tools escanea o adjunta archivos del
proyecto por su cuenta, así que lo que se manda a la nube es exactamente lo
que el que llama escribió en `task`, nada más.

Enrutamiento (LOCAL vs. OpenCode vs. cloud) documentado en el system prompt
del agente (app/agent.py), no acá -- ver ese docstring para el criterio real
(corregido 2026-08-12: OpenCode hoy comparte el mismo modelo que Jarvis, así
que "modelo más potente" todavía no aplica)."""

from __future__ import annotations

from .. import audit_log
from ..cloud_client import client
from ..config import settings
from . import register_tool

_MAX_OUTPUT_TOKENS = 4096

_CODE_SYSTEM_PROMPT = (
    "Sos un asistente experto en escritura de código. Te piden un PRIMER BORRADOR de código real "
    "para una tarea puntual -- otro sistema (Jarvis) va a auditar, corregir y testear este borrador "
    "después, así que priorizá corrección real (APIs/clases/métodos que existen de verdad, no "
    "inventados) por sobre pulido de estilo. Si no estás seguro de una API específica, preferí una "
    "forma más simple pero real. Devolvé el código directamente, con una explicación breve si hace "
    "falta contexto, sin relleno innecesario."
)

_MARKETING_SYSTEM_PROMPT = (
    "Sos un asistente experto en redacción de marketing técnico (posts para comunidades como Reddit "
    "r/LocalLLaMA, READMEs de proyectos open source, guiones de demo, textos de posicionamiento). "
    "Escribí contenido real y específico para lo que te pidan, en el tono que corresponda al canal "
    "(técnico y directo para una comunidad técnica, no genérico de marketing corporativo)."
)


class CloudExpertNotConfigured(RuntimeError):
    pass


class CloudExpertSensitiveDataBlocked(PermissionError):
    pass


async def _ask_gemini(system_prompt: str, task: str) -> str:
    response = await client.chat.completions.create(
        model=settings.google_ai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ],
        max_tokens=_MAX_OUTPUT_TOKENS,
    )
    return response.choices[0].message.content or ""


def _check_configured_and_confirmed(tool_name: str, task: str, confirm_non_sensitive: bool) -> dict:
    arguments = {"task": task, "confirm_non_sensitive": confirm_non_sensitive}

    if not settings.google_ai_api_key:
        error = (
            "GOOGLE_AI_API_KEY no está configurada en backend/.env -- generá una gratis en "
            "https://aistudio.google.com/apikey y agregala ahí para habilitar esta tool."
        )
        audit_log.log_tool_call(target="cloud", tool=tool_name, arguments=arguments, error=error)
        raise CloudExpertNotConfigured(error)

    if not confirm_non_sensitive:
        error = (
            "Esta tool manda 'task' a un proveedor externo (Gemini, Google AI Studio) -- se necesita "
            "confirm_non_sensitive=true explícito para confirmar que la tarea NO incluye código "
            "propietario, datos de proyectos reales de clientes, ni información sensible. Nunca lo "
            "pongas en true por default -- confirmalo solo cuando de verdad sea una tarea no sensible "
            "(ej. un proyecto nuevo/de prueba, contenido de marketing genérico)."
        )
        audit_log.log_tool_call(target="cloud", tool=tool_name, arguments=arguments, error=error)
        raise CloudExpertSensitiveDataBlocked(error)

    return arguments


@register_tool(
    name="cloud_expert_code",
    description=(
        "Pide a Gemini Flash (API gratuita de Google AI Studio) un PRIMER BORRADOR de código real "
        "para una tarea puntual -- pensado para proyectos NUEVOS/NO SENSIBLES donde el modelo local "
        "viene fallando por falta de conocimiento de una API específica (mismo problema que resolvió "
        "la referencia curada de Fabric para opencode_run_task, pero para casos donde no hay una "
        "referencia curada armada todavía). Devuelve SOLO texto -- no escribe ningún archivo. Vos "
        "seguís siendo responsable de todo el ciclo después: escribir el código de verdad "
        "(fs_write_file/code_apply_fix), auditarlo (security_scan_project) y testearlo "
        "(code_run_tests/security_audit_find_fix_verify) -- esta tool NUNCA reemplaza ese ciclo, solo "
        "mejora el punto de partida. Requiere confirm_non_sensitive=true explícito (la tarea sale de "
        "la máquina hacia un proveedor externo) y GOOGLE_AI_API_KEY configurada en backend/.env."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Descripción de la tarea de código -- lo único que se manda a Gemini, tal cual.",
            },
            "confirm_non_sensitive": {
                "type": "boolean",
                "description": (
                    "true SOLO si confirmaste que 'task' no incluye código propietario ni datos "
                    "sensibles de un proyecto real de cliente. Default false -- nunca lo pongas en "
                    "true automáticamente."
                ),
            },
        },
        "required": ["task", "confirm_non_sensitive"],
    },
)
async def cloud_expert_code(task: str, confirm_non_sensitive: bool = False) -> dict:
    arguments = _check_configured_and_confirmed("cloud_expert_code", task, confirm_non_sensitive)
    try:
        draft = await _ask_gemini(_CODE_SYSTEM_PROMPT, task)
    except Exception as exc:
        audit_log.log_tool_call(target="cloud", tool="cloud_expert_code", arguments=arguments, error=str(exc))
        raise
    result = {"draft": draft, "model": settings.google_ai_model}
    audit_log.log_tool_call(target="cloud", tool="cloud_expert_code", arguments=arguments, result=result)
    return result


@register_tool(
    name="cloud_expert_marketing",
    description=(
        "Pide a Gemini Flash (API gratuita de Google AI Studio) un borrador de contenido de "
        "marketing/comunicación real (posts para comunidades técnicas, READMEs, guiones de demo, "
        "textos de posicionamiento) -- combinable con generate_image para separar quién escribe el "
        "copy de quién genera la imagen final. Devuelve SOLO texto, ningún efecto secundario. "
        "Requiere confirm_non_sensitive=true explícito y GOOGLE_AI_API_KEY configurada en backend/.env."
    ),
    parameters={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "Descripción de la tarea de redacción -- lo único que se manda a Gemini, tal cual.",
            },
            "confirm_non_sensitive": {
                "type": "boolean",
                "description": (
                    "true SOLO si confirmaste que 'task' no incluye información sensible. Default "
                    "false -- nunca lo pongas en true automáticamente."
                ),
            },
        },
        "required": ["task", "confirm_non_sensitive"],
    },
)
async def cloud_expert_marketing(task: str, confirm_non_sensitive: bool = False) -> dict:
    arguments = _check_configured_and_confirmed("cloud_expert_marketing", task, confirm_non_sensitive)
    try:
        draft = await _ask_gemini(_MARKETING_SYSTEM_PROMPT, task)
    except Exception as exc:
        audit_log.log_tool_call(target="cloud", tool="cloud_expert_marketing", arguments=arguments, error=str(exc))
        raise
    result = {"draft": draft, "model": settings.google_ai_model}
    audit_log.log_tool_call(target="cloud", tool="cloud_expert_marketing", arguments=arguments, result=result)
    return result
