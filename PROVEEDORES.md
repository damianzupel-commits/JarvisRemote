# 🧺 PROVEEDORES — Los proveedores de ingredientes de la cocina

> Registro de proveedores externos de Raphael: los servicios y dependencias de
> los que la cocina consume "ingredientes" (modelos, red, inteligencia de
> amenazas, paquetes, entornos de práctica, voz, etc.).
> Creado el 2026-08-24. Mantenelo al día cuando sumes o saques un proveedor.

## Qué es esto

Siguiendo la metáfora de cocina del proyecto, este documento lista a **quién le
compra Raphael los ingredientes** que no produce él mismo. Un ingrediente es
cualquier cosa que la cocina consume de afuera: los modelos LLM que piensan, la
red privada que conecta todo, la inteligencia de amenazas que consulta, los
paquetes de Python que instala, los entornos vulnerables donde practica, la voz
del co-host, etc.

## Por qué importa

Saber a quién le comprás te da tres cosas: **control de costos** (saber qué es
gratis, qué se paga por token y dónde puede escaparse la cuenta), **claridad de
dependencias** (qué necesita cuenta o API key para funcionar) y **resiliencia**
(si un proveedor se cae, sube el precio o cambia los términos, ya tenés
identificado el respaldo y no te quedás sin servicio). Un cocina que no sabe de
dónde vienen sus ingredientes se queda a pie el día que falla el reparto.

## La tabla de proveedores

| Proveedor | Qué provee (ingrediente) | Costo | ¿Cuenta/key necesaria? | Criticidad | Proveedor de respaldo |
|---|---|---|---|---|---|
| **OpenRouter** | Modelos LLM — el cerebro (DeepSeek V4 texto + qwen/qwen3.7-flash visión) | Pago por token (~centavos) | Sí — API key + crédito | **Alta** | DeepInfra, Together, Fireworks |
| **Tailscale** | Red privada (VPN sobre WireGuard) | Free tier | Sí — cuenta | Media | WireGuard configurado a mano |
| **VirusTotal** | Inteligencia de amenazas (consulta por hash) | Free tier | Sí — API key | Media | Análisis local (YARA / ClamAV) |
| **Microsoft Defender** | Antivirus base + ASR | Gratis (built-in de Windows) | No | **Alta** | ClamAV |
| **Herramientas de seguridad** (nmap, sqlmap, ZAP, ClamAV, Metasploit) | Motores de escaneo / pentest | Gratis / open source | No | **Alta** | Alternativas open source equivalentes |
| **Blancos vulnerables** (Metasploitable, DVWA, OWASP Juice Shop, VulnHub, GOAD) | Entornos de práctica | Gratis | No | Media | Entre ellos |
| **Atomic Red Team / MITRE Caldera** | Emulación de adversarios | Gratis / open source | No | Media | Entre ellos |
| **VirtualBox** | Virtualización del cyber range | Gratis | No | Media | VMware Workstation, Hyper-V |
| **GitHub** | Repositorio + respaldo remoto (privado) | Gratis | Sí — cuenta | **Alta** | Respaldo local + otro remoto (GitLab) |
| **PyPI (pip)** | Paquetes de Python | Gratis | No | **Alta** | Mirror |
| **YouTube** | Contenido / ideas (playlist "Info para Jarvis") | Gratis | No (cuenta solo para la playlist) | Baja | n/a |
| **LM Studio (local)** | Embeddings (nomic) | Gratis, local | No | Media | Otro modelo de embeddings |
| **Ollama (local)** | Modelo local de respaldo (jarvis-text-v2 / qwen3-30b) | Gratis, local | No | Baja (ahora que el cerebro es OpenRouter) | El propio OpenRouter |
| **ElevenLabs** *(a futuro)* | Voz TTS del co-host | Pago | Sí — API key | Baja | Piper (local, gratis) |

## Reglas de proveedor

1. **Toda key de un proveedor pago va cifrada o en `.env`, nunca en el código ni
   en el chat.** Si un proveedor requiere API key (OpenRouter, VirusTotal,
   ElevenLabs), la clave vive en `backend/.env` (gitignoreado) o cifrada — jamás
   hardcodeada ni pegada en una conversación.
2. **Los proveedores "gratis e ilimitados" de modelos casi siempre entrenan con
   tus datos.** Si algo es gratis y no tiene límite claro, la moneda de pago sos
   vos: NO usar esos proveedores con datos sensibles, de clientes o de targets de
   pentesting.
3. **Para todo lo crítico, tener siempre un respaldo identificado.** Ningún
   ingrediente de criticidad alta debería depender de un solo proveedor sin plan
   B ya escrito en la columna de respaldo de arriba.
