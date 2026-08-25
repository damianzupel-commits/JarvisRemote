# PLAN DE NEGOCIO — 2 MESES AL PRIMER INGRESO

## Servicio productizado: "Blindaje de Seguridad para PyMEs"

> **Autor:** documento de estrategia para Damian.
> **Fecha:** 2026-08-17.
> **Alcance:** SOLO estrategia y negocio. No ejecuta nada técnico, no instala,
> no toca código. El detalle técnico de la entrega vive en
> `lab/DEFENSA-PRIORIDADES.md` y `lab/DEFENSA-KERNEL-GRATIS-DESIGN.md`.
> **Ubicación del negocio:** sin confirmar. Los precios están escritos como
> **framework adaptable** (método + rangos de ejemplo en USD + cómo localizar),
> con un `Rosario` para tu mercado. Ningún precio local se da como
> cierto.

---

## Aviso honesto (leé esto primero)

Este plan **no garantiza ingreso**. Ningún plan puede. Lo que hace es
**maximizar la probabilidad** de conseguir tus primeros 2–3 clientes en ~60 días,
ordenando el trabajo para que cada día empuje hacia una venta real y no hacia
"seguir puliendo el producto". La mayor causa de fracaso en este tipo de lanzamiento
no es la técnica —que ya dominás— sino **no vender**: pulir demasiado, no prospectar,
no cerrar. El plan está sesgado a la acción comercial a propósito.

Segundo aviso: el lado **ofensivo (pentesting) NO se vende como producto**. Solo se
vende lo **defensivo**. Y **todo** trabajo sobre el sistema de un cliente requiere
**autorización firmada** antes de tocar nada. Esto no es opcional ni un tecnicismo:
acceder a un sistema ajeno sin autorización escrita es delito en la mayoría de las
jurisdicciones (en EE.UU. el Computer Fraud and Abuse Act; equivalentes en casi
todos los países). La autorización te protege legalmente y ordena el alcance.

---

## 1. Resumen ejecutivo + tesis

### La oferta en una frase

Le instalás a una PyME la **misma pila de defensa nativa de Windows que ya sabés
configurar** —Defender a full + Tamper Protection, reglas ASR, AppLocker, AMSI,
Sysmon— con **costo de herramientas = cero**, cobrás un **setup único** por dejarlo
blindado y un **abono mensual** por vigilarlo y mantenerlo. Precio fijo, alcance
fijo, entregable claro (informe antes/después).

### La tesis (por qué esto y por qué ahora)

1. **El mercado paga y el dolor es real.** El 88% de las brechas en PyMEs hoy
   involucran ransomware (vs. 39% en grandes empresas), y dos tercios de los ataques
   de ransomware apuntan a empresas de menos de 500 personas. El 60% de las PyMEs
   atacadas cierran dentro de los 6 meses. Y el dato que vende solo: **prevenir cuesta
   50–60× menos que recuperarse** (~USD 5.000–15.000/año de prevención vs. USD 500.000+
   por un solo incidente). Vos podés dar esa prevención con herramientas gratis.

2. **Tu ventaja es asimétrica.** El costo de tus herramientas es cero (todo es nativo
   de Windows), así que tu margen es casi todo el precio. Un MSSP tradicional revende
   licencias caras; vos vendés **conocimiento y ejecución**. Eso te permite entrar
   por debajo del mercado y seguir teniendo margen altísimo.

3. **El servicio es un puente al producto.** Cada entrega manual que hacés es una
   **especificación viva** de lo que Jarvis va a automatizar. Los primeros clientes
   te pagan por hacer a mano lo que después el software hará solo. No estás eligiendo
   entre "servicio" y "producto": el servicio **financia y define** el producto
   (ver §8). Es el camino clásico servicio → productized service → semi-producto → MSP.

4. **El formato "productized service" acorta el ciclo de venta.** Paquete cerrado,
   precio público, entregable definido: el cliente sabe exactamente qué recibe y por
   cuánto. Publicar tiers, tiempos de entrega y qué incluye/qué no dejó de ser un
   diferenciador y pasó a ser una expectativa en 2026; los que lo hacen ganan confianza
   y cierran más rápido.

### Qué tenés que creer para que esto funcione

Que sos capaz de **explicarle a un dueño de PyME, sin jerga, por qué su computadora
está expuesta y qué le cambia tu trabajo** — y que vas a dedicar el Mes 2 a **hablar
con gente**, no a programar. Si el Mes 2 lo pasás codeando, el plan falla.

---

## 2. Definición del paquete

### Nombre

**"Blindaje PyME"** (nombre de trabajo). Alternativas para probar en la landing:
"Escudo PyME", "Blindaje Windows", "PyME Segura". Elegí uno y usalo consistente.

### Qué incluye (mapeado al checklist técnico)

Todo sale de `lab/DEFENSA-PRIORIDADES.md`. Traducido a lenguaje de cliente:

| Lo que hacés (técnico) | Cómo se lo vendés al cliente |
|---|---|
| **Paso 0:** Defender a full (RTP, Behavior, Cloud, script scanning) + **Tamper Protection** | "Dejamos tu antivirus de Windows en su máxima potencia y lo blindamos para que ni un virus ni un atacante puedan apagarlo." |
| **Reglas ASR** (audit → block: LSASS, Office→hijos, ejecutables de email/USB) | "Bloqueamos las cadenas de ataque más comunes: robo de contraseñas, archivos peligrosos que llegan por mail o pendrive, macros de Office maliciosas." |
| **AppLocker** (audit largo → block) | "Solo corre en tus PCs el software autorizado. Un troyano descargado por error simplemente no arranca." |
| **AMSI** (fileless / scripts) | "Detenemos ataques que viven en la memoria y no dejan archivo — el tipo de amenaza que un antivirus común no ve." |
| **Sysmon** (capa sensorial) | "Instalamos una caja negra que registra lo que pasa en el sistema, para poder detectar y responder si algo raro ocurre." |
| **Informe antes/después** + monitoreo mensual | "Te entregamos un informe claro de cómo estabas y cómo quedaste, y lo revisamos todos los meses." |

**Regla de entrega no negociable (viene del checklist):** todo lo que bloquea (ASR,
AppLocker) va **primero en modo AUDITORÍA**, se observa que no rompa software legítimo
del cliente, y **recién después** se pasa a bloqueo. Esto es a la vez buena práctica
técnica y **argumento de venta**: "no te voy a romper el sistema, primero observo".

### Qué NO incluye (límites explícitos)

- **NO pentesting / nada ofensivo.** No escaneás, no explotás, no atacás. Solo defensa.
- **NO** WDAC en enforce ni WFP en los primeros clientes (esfuerzo alto/avanzado; se
  suman más adelante como upsell cuando el proceso esté maduro).
- **NO** respuesta a incidentes 24/7 activa (no sos un SOC; sos prevención + revisión
  mensual). Sé honesto: es "blindaje + vigilancia periódica", no "alguien mirando a las 3am".
- **NO** soporte de IT general (no arreglás impresoras, no configurás mail). Alcance fijo.
- **NO** garantía de invulnerabilidad. Reducís drásticamente el riesgo; no lo eliminás.

### Tiers (3 niveles)

Empaquetá en tres niveles fijos. Anclá con el del medio (es el que más se compra).

**TIER 1 — Blindaje Básico**
- Paso 0 (Defender full + Tamper) + reglas ASR clave (audit→block) en hasta *N* PCs.
- Informe antes/después.
- Sin abono obligatorio (o abono mínimo opcional).
- *Objetivo:* punto de entrada barato, para el que "solo quiere estar cubierto".

**TIER 2 — Blindaje Completo** *(el recomendado, el que anclás)*
- Todo lo de Tier 1 + AppLocker (audit→block) + AMSI + Sysmon.
- Informe antes/después detallado.
- **Abono mensual** de monitoreo: revisión de logs, ajuste de reglas, reporte mensual.
- *Objetivo:* el paquete estrella. La mayoría debería comprar esto.

**TIER 3 — Blindaje Gestionado**
- Todo lo de Tier 2 + más PCs, revisión más frecuente, onboarding de nuevos equipos,
  y ruta a WDAC/WFP cuando corresponda.
- Abono mensual más alto.
- *Objetivo:* cliente con más equipos o más sensible (clínica, estudio contable grande).

### Entregable

El artefacto que justifica el precio y genera el boca a boca:

**Informe "Antes / Después"** (PDF, ~4–8 páginas, plantilla reutilizable):
1. Estado inicial: qué defensas estaban apagadas o a medias (con capturas).
2. Qué se aplicó, explicado en lenguaje simple.
3. Estado final: checklist verde de lo que ahora está activo.
4. Qué queda fuera de alcance y qué recomendás a futuro.
5. Qué cubre el abono mensual.

Este informe **es** el producto tangible. Es lo que el cliente muestra, lo que
justifica el precio y lo que reusás cliente tras cliente.

---

## 3. Precios (framework adaptable)

> **Importante:** los números de abajo son **rangos de ejemplo en USD** basados en el
> mercado global de servicios de seguridad para PyMEs (2026). **No son precios de
> `Rosario`.** Usá el método para fijar el tuyo y adaptá con los
> factores de localización.

### Referencias del mercado 2026 (para calibrar, no para copiar)

- **MSSP para PyMEs:** típicamente **USD 2.000–5.000/mes**.
- **Por endpoint:** SOC-as-a-service **USD 8–25/endpoint/mes**; MDR para PyMEs
  **USD 10–25**; algunos proveedores **USD 25–75/endpoint/mes**.
- **Por usuario:** **USD 50–200+/usuario/mes** según profundidad.
- **Retainers chicos:** base **USD 3.000–10.000/mes** + horas/proyecto.

Estos números son de EE.UU./mercados maduros y de servicios con licencias caras
incluidas. **Tu costo de herramientas es cero**, así que tu piso puede ser mucho más
bajo y tu margen igual altísimo. Usalos como **techo de referencia**, no como objetivo.

### El método para fijar TU precio (5 pasos)

1. **Calculá tu piso por hora.** Estimá cuánto necesitás ganar por hora de trabajo
   real (mirá lo que cobra un dev senior por hora en `Rosario` y usalo
   como referencia). Ese es tu piso: nunca cobres el setup por debajo de (horas
   estimadas × tu piso).
2. **Estimá el esfuerzo del setup.** Un Tier 2 en 3–5 PCs, con audit → block hecho
   con cuidado, informe incluido: estimá horas honestas (probablemente 8–16h las
   primeras veces, bajando con la práctica). Setup = horas × piso, redondeado hacia
   arriba.
3. **Precio por outcome, no por hora (para el número público).** El cliente no compra
   horas, compra "no cerrar por un ransomware". Anclá el precio al **valor** (evitar
   una pérdida de decenas o cientos de miles) — pero usá el piso por hora del paso 1
   como red de seguridad para no perder plata.
4. **Separá setup (único) de abono (recurrente).** El **setup** paga el trabajo
   intenso inicial. El **abono** paga la tranquilidad continua (revisión, ajustes,
   reporte). El abono es lo que construye ingreso predecible y es la semilla del MSP.
5. **Publicá los tres tiers con precio.** Transparencia = ciclo de venta más corto.
   Anclá con el Tier 2.

### Rangos de ejemplo (USD — AJUSTAR a tu mercado)

| Concepto | Tier 1 Básico | Tier 2 Completo | Tier 3 Gestionado |
|---|---|---|---|
| **Setup (pago único)** | USD 150–400 | USD 400–900 | USD 900–2.000 |
| **Abono (mensual)** | USD 0–40 | USD 60–150 | USD 150–400 |

> Estos son **ejemplos de estructura**, calibrados por debajo del mercado MSSP porque
> tu costo de herramientas es cero y sos nuevo (necesitás los primeros casos). En
> `Rosario` el poder adquisitivo puede ser muy distinto — **es
> esperable dividir estos números** en economías con salarios más bajos. No los tomes
> como verdad local.

### Cómo localizar el precio

- **Anclá al salario local, no al dólar global.** Si un dev senior en tu ciudad cobra
  X/mes, tu setup debería sentirse "razonable" contra ese X, no contra el mercado de EE.UU.
- **Cobrá en la moneda que te proteja de la inflación** si aplica (ej. algunos mercados
  facturan servicios en USD o ajustan mensual). Decisión tuya según `Rosario`.
- **Test de las tres reacciones.** Al decir el precio: si TODOS dicen "sí, barato" →
  subilo. Si TODOS se van → bajalo o cambiá el segmento. Si ~1 de 3 duda pero compra →
  estás bien.
- **Nunca compitas por precio siendo el más barato.** Competí por **claridad y confianza**.
  El más barato atrae al peor cliente.

### Lógica setup + abono (por qué esta estructura)

El **setup único** captura el trabajo de dejar el sistema blindado — es intenso y de
una vez. El **abono mensual** vende **tranquilidad recurrente** (revisar que las reglas
sigan bien, ajustar ante software nuevo, reporte). Sin abono tenés que revender cada
mes; con abono construís ingreso predecible **y** es exactamente lo que evoluciona
hacia un MSP. **Meta comercial: que la mayoría de los Tier 2/3 tomen el abono.**

---

## 4. Cliente objetivo

### Quién (PyMEs con datos sensibles y baja tolerancia a caer)

Apuntá a negocios chicos (aprox. 3–30 PCs) que (a) **manejan datos sensibles**, (b)
**no pueden operar si se caen**, y (c) **no tienen IT interno serio**:

- **Estudios contables / gestorías** — datos fiscales de terceros, deadlines duros.
- **Clínicas, consultorios, odontólogos** — datos de salud, obligaciones de privacidad.
- **Estudios jurídicos / escribanías** — confidencialidad como núcleo del negocio.
- **Inmobiliarias, aseguradoras chicas** — datos personales y financieros de clientes.
- **Comercios/PyMEs con e-commerce o mucho dato de clientes** — pagos, base de datos.
- **Consultoras chicas, agencias** — propiedad intelectual de clientes.

### Por qué pagan

- **Miedo concreto y fundado:** un ransomware les frena la facturación y puede fundirlos
  (60% cierra en 6 meses). El dueño lo intuye pero no sabe qué hacer.
- **Obligación / responsabilidad:** manejan datos de terceros; una filtración es un
  problema legal y reputacional, no solo técnico.
- **No tienen a quién llamar:** demasiado chicos para un depto de IT, demasiado
  expuestos para no hacer nada. Sos exactamente el tamaño de solución que les falta.
- **Prevención barata vs. desastre caro:** el argumento 50–60× es el más fuerte.

### Cómo detectarlas (señales de buen prospecto)

- Usan Windows en todas las PCs (tu pila es Windows-nativa — descartá los 100% Mac).
- Tienen datos regulados o confidenciales (salud, fiscal, legal, financiero).
- Sin IT interno o con "el sobrino que sabe de computadoras".
- El dueño toma la decisión (ciclo corto — no hay comité).
- Ya tuvieron un susto (virus, cuenta hackeada, mail comprometido) → urgencia real.
- Están en tu red cercana o a un contacto de distancia (empezá por acá — ver Mes 2).

### Anti-cliente (a quién NO perseguir al principio)

Empresas grandes con IT propio (ciclo largo, te piden certificaciones), quien solo
quiere lo más barato, entornos 100% no-Windows, y cualquiera que pida servicios
ofensivos. Decir que no a estos te ahorra semanas.

---

## 5. PLAN DÍA POR DÍA — MES 1 (ARMAR)

> Suposición: dedicás ~3–5 h/día. Si tenés menos, estirá los bloques pero **no saltees
> el orden**. Los fines de semana son colchón/descanso. Cada día tiene un entregable.
> El principio rector del Mes 1: **construir una vez lo que vas a reusar en cada cliente.**

### Semana 1 — Definir la oferta y el proceso repetible

**Día 1 — Congelar la oferta.**
Escribí en una página: nombre elegido, los 3 tiers, qué incluye/qué no cada uno,
y el precio (usando §3). No lo pulas: decidilo. Entregable: `oferta.md` de una página.

**Día 2 — Guion de entrega repetible (parte 1).**
Convertí `lab/DEFENSA-PRIORIDADES.md` en un **checklist operativo de entrega**: pasos
ordenados (Paso 0 → ASR audit → observar → ASR block → AppLocker audit → …), con el
comando/acción de cada paso y el criterio de "listo". Este es tu SOP: lo que hacés
idéntico en cada cliente. Entregable: `runbook-entrega.md` (Paso 0 + ASR).

**Día 3 — Guion de entrega repetible (parte 2).**
Completá el runbook: AppLocker (audit largo → block), AMSI, Sysmon, y la fase de
verificación. Incluí la **regla audit-antes-de-block** como paso explícito y qué
observar antes de pasar a enforce (que no rompa software legítimo del cliente).
Entregable: `runbook-entrega.md` completo.

**Día 4 — Plantilla del informe Antes/Después.**
Diseñá la plantilla del entregable (estructura de §2). Dejá huecos para capturas y un
checklist verde. Que se vea profesional y simple. Entregable: `plantilla-informe.md`
(o .docx).

**Día 5 — Plantilla de contrato + autorización.**
Adaptá el borrador de §10 a tu jurisdicción (placeholder para revisión legal local).
Debe tener: alcance exacto, cláusula de **autorización escrita** para trabajar sobre
sus sistemas, límites (solo defensivo), datos/confidencialidad, precio setup+abono,
y limitación de responsabilidad. Entregable: `contrato-plantilla.md`.

### Semana 2 — Probarlo en un caso real y sacar prueba social

**Día 6 — Caso de prueba (elegí el conejillo).**
Elegí un entorno real para correr el runbook completo de punta a punta: tu propia PC,
la de un familiar, o un conocido que te deje (con autorización firmada, aunque sea
gratis). Objetivo: **cronometrar y encontrar los baches del proceso.**

**Día 7 — Ejecutar el caso de prueba.**
Corré el runbook entero sobre ese entorno. Anotá cuánto tardás en cada paso, qué se
rompió, qué falta en el runbook. Sacá las capturas del antes.

**Día 8 — Cerrar el caso + primer informe real.**
Terminá el blindaje, sacá capturas del después, y **generá el primer informe Antes/
Después de verdad** con la plantilla. Este informe es tu **muestra de portfolio**
(anonimizado). Entregable: informe #0.

**Día 9 — Refinar runbook e informe con lo aprendido.**
Corregí el SOP con los baches del caso real. Ajustá la estimación de horas del setup
(y por lo tanto el precio, si hace falta). Ahora tu proceso es real, no teórico.

**Día 10 — Pedir el primer testimonio.**
Si el caso de prueba fue con un conocido, pedile un testimonio corto ("me dejó las
PCs blindadas, me explicó todo claro"). Si fue tu PC, escribí un mini caso de estudio
anonimizado. Necesitás **algo** que mostrar. Entregable: 1 testimonio o mini-caso.

### Semana 3 — Presencia mínima y materiales de venta

**Día 11 — Copy de la landing (borrador en §ANEXO A).**
Adaptá el borrador de landing de este documento a tu oferta y ciudad. No la construyas
todavía — primero el texto. Entregable: `landing-copy.md`.

**Día 12 — Construir la landing de una página.**
Página simple (Carrd, Notion público, o HTML propio — barato/gratis). Secciones:
problema, solución, 3 tiers con precio, informe de muestra, testimonio, y un botón de
contacto (WhatsApp/mail/formulario). Publicala. Entregable: URL viva.

**Día 13 — Perfil de LinkedIn orientado a la oferta.**
Reescribí tu headline y "acerca de" en LinkedIn para que diga qué hacés por PyMEs (no
"desarrollador" genérico). Un post de lanzamiento explicando el problema del ransomware
en PyMEs y que ayudás a blindarlas. Entregable: perfil + 1 post.

**Día 14 — Mensaje de prospección (borrador en §ANEXO B).**
Adaptá el mensaje de contacto de este documento. Preparworks 2 versiones: una para
**red cercana** (cálida) y una para **frío local** (a un negocio que no te conoce).
Entregable: `mensajes-prospeccion.md`.

### Semana 4 — Pitch, lista de prospectos y ensayo

**Día 15 — Pitch de 2 minutos.**
Escribí y memorizá tu pitch hablado: problema (ransomware funde PyMEs) → por qué ellos
(datos sensibles, sin IT) → qué hacés (blindaje con herramientas que ya tienen, costo
cero de licencias) → qué reciben (informe + tranquilidad) → precio. Practicalo en voz alta.

**Día 16 — Manejo de objeciones.**
Escribí respuestas a las 6 objeciones típicas (§6). Memorizalas. "Ya tengo antivirus",
"es caro", "nunca me pasó nada", "no entiendo de esto", "¿y si me rompés algo?",
"mándame info por mail". Entregable: `objeciones.md`.

**Día 17 — Construir la lista de prospectos.**
Listá **30–50 prospectos concretos**: primero red cercana (conocidos con negocio,
familiares, ex-colegas), después PyMEs locales que encajen en §4 (contadores, clínicas,
estudios de tu zona — Google Maps + LinkedIn). Columnas: nombre, rubro, contacto, cómo
llegás (cálido/frío), estado. Entregable: `prospectos.csv`.

**Día 18 — Preparar el "kit de venta".**
Junta todo en una carpeta lista para mostrar: link a landing, informe de muestra,
testimonio, contrato-plantilla, y los mensajes. Que puedas mandarlo en 30 segundos.

**Día 19 — Ensayo general + track freelance.**
Ensayá el pitch con alguien de confianza que te dé feedback honesto. En paralelo, abrí
perfiles en las plataformas freelance (§7) para el track de caja. Entregable: perfiles
freelance creados.

**Día 20 — Revisión de fin de Mes 1.**
Checklist: ¿oferta congelada? ¿runbook probado? ¿informe de muestra? ¿landing viva?
¿LinkedIn? ¿contrato? ¿30–50 prospectos? ¿pitch memorizado? Si algo falta, **este es
el día de cerrarlo**. Mañana empezás a vender.

> **Salida del Mes 1:** tenés un producto empaquetado, un proceso repetible probado en
> un caso real, materiales de venta, y una lista de gente a quien contactar. No
> escribiste una línea de producto nuevo — reusaste lo que ya sabés.

---

## 6. PLAN DÍA POR DÍA — MES 2 (VENDER Y ENTREGAR)

> Regla de oro del Mes 2: **contactar gente todos los días.** La métrica que importa no
> es "cuánto puliste" sino "cuántas conversaciones de venta tuviste". Meta: **2–3
> clientes** y el **primer ingreso**. Empezás por la red cercana (convierte mucho más)
> y recién después vas a frío.

### Semana 5 — Prospección cálida (red cercana primero)

**Día 21 — Primeros 10 contactos cálidos.**
Mandá el mensaje cálido (§ANEXO B) a los 10 prospectos más cercanos de tu lista. No
vendas en el primer mensaje: pedí una charla de 15 min. Registrá cada envío en el CSV.

**Día 22 — Seguir contactando + primeras respuestas.**
Otros 10 contactos cálidos. Respondé a los que contestaron, agendá llamadas/cafés.

**Día 23 — Primeras reuniones de venta.**
Tené 1–3 conversaciones. Usá el pitch, escuchá su dolor, mostrá el informe de muestra.
No cierres a presión: entendé si encajan. Ofrecé mandar la propuesta (los 3 tiers).

**Día 24 — Enviar propuestas + seguimiento.**
A quienes mostraron interés, mandales la propuesta simple (tier recomendado + precio +
qué incluye + próximo paso). Seguí contactando prospectos nuevos en paralelo.

**Día 25 — Pedir referidos + cerrar lo cálido.**
Pedí a todos —compren o no— **un referido**: "¿conocés a alguien con un negocio a quien
le sirva esto?". Los referidos convierten muchísimo. Intentá cerrar el primer cliente.

### Semana 6 — Primer cierre y primera entrega

**Día 26 — Cerrar el primer cliente.**
Cuando alguien diga que sí: mandá el **contrato + autorización** (§10), que lo firme
**antes** de tocar nada. Cobrá el setup (o una seña) por adelantado o contra entrega,
según acuerdes — pero dejá el cobro pactado por escrito.

**Día 27 — Agendar y preparar la entrega.**
Agendá la ventana de trabajo. Repasá el runbook para ese cliente puntual (cuántas PCs,
qué software usan — para no romper nada en el enforce). Confirmá que la autorización
está firmada.

**Día 28 — Entregar (parte 1: Paso 0 + ASR audit).**
Ejecutá: Defender full + Tamper, y ASR en **audit**. Sacá capturas del antes. Dejá el
audit corriendo el tiempo necesario (no pases a block el mismo día — respetá la regla).

**Día 29 — Seguir vendiendo mientras el audit corre.**
No frenes la prospección por tener un cliente. Otros 10 contactos (cálidos + primeros
fríos locales). El objetivo son 2–3 clientes, no uno.

**Día 30 — Entregar (parte 2: revisar audit → block + AppLocker audit).**
Revisá qué habría bloqueado el ASR en audit; si no rompe nada legítimo, pasá a block
las reglas clave (LSASS, Office→hijos). Arrancá AppLocker en audit.

### Semana 7 — Cerrar la entrega, cobrar, y segundo cliente

**Día 31 — Entregar (parte 3: AMSI + Sysmon + AppLocker block).**
Completá AMSI y Sysmon. Pasá AppLocker a block si el audit está limpio. Verificá que
todo el software del cliente sigue funcionando.

**Día 32 — Informe Antes/Después + entrega formal.**
Generá el informe con la plantilla, capturas antes/después, checklist verde. Presentáselo
al cliente en persona/videollamada — **este es el momento de mayor valor percibido.**

**Día 33 — Cobrar el setup + activar el abono.**
Cobrá el setup completo. Proponé el **abono mensual** como continuación natural: "para
que esto siga protegido y ajustado, lo reviso todos los meses por {precio}/mes".
Dejá el abono activado por escrito. **Este es tu primer ingreso — y el primer recurrente.**

**Día 34 — Pedir testimonio + referido al cliente entregado.**
Cliente satisfecho y recién entregado = mejor momento para pedir testimonio y 1–2
referidos. Sumá el testimonio real a la landing (reemplaza al del caso de prueba).

**Día 35 — Empujar el segundo cierre.**
Retomá las propuestas pendientes de la semana 5–6. Con un caso real entregado y un
testimonio fresco, tu credibilidad subió. Intentá cerrar el segundo cliente.

### Semana 8 — Escalar a 2–3 clientes y consolidar

**Día 36 — Prospección fría local.**
Ahora sí, frío: visitá o escribí a PyMEs locales de tu lista (contadores, clínicas,
estudios). Mensaje frío (§ANEXO B). Presencial suele funcionar mejor que mail en frío.

**Día 37 — Segunda entrega (si cerraste el 2º cliente).**
Repetí el proceso. Ahora es más rápido: el runbook ya está afinado.

**Día 38 — Seguir la segunda entrega + tercer prospecto.**
Avanzá la entrega y mantené 1–2 conversaciones nuevas para el tercer cliente.

**Día 39 — Cerrar segunda entrega + cobrar + abono.**
Informe, cobro del setup, activar abono. Segundo ingreso. Pedí testimonio y referido.

**Día 40 — Revisión de fin de Mes 2.**
Balance: ¿cuántos clientes cerraste? ¿cuánto cobraste (setup)? ¿cuántos abonos activos?
¿cuántos prospectos en el pipeline? Ajustá precio y oferta con lo aprendido. Planificá
el mes 3 (más clientes + empezar a automatizar — §8).

> **Salida del Mes 2 (objetivo):** 2–3 clientes entregados, **primer ingreso cobrado**,
> 2–3 abonos mensuales activos (ingreso recurrente naciente), testimonios reales, y un
> pipeline de referidos. Y un runbook tan afinado que ya sabés exactamente qué partes
> Jarvis puede automatizar (§8).

### Guion de venta (estructura de la conversación)

1. **Abrir con el dolor, no con la técnica:** "¿Sabías que el 60% de las PyMEs que
   sufren un ransomware cierran en 6 meses? Y la mayoría de los ataques hoy son a
   empresas chicas, no a las grandes."
2. **Conectar con ELLOS:** "Vos manejás [datos fiscales / de pacientes / de clientes].
   Si mañana no podés abrir esos archivos, ¿qué pasa con tu operación?"
3. **La solución simple:** "Windows ya trae defensas potentes, pero vienen a media
   máquina. Yo las dejo al 100% y blindadas para que ni un virus las pueda apagar.
   Sin comprar licencias — uso lo que ya tenés."
4. **El entregable:** "Te dejo un informe claro de cómo estabas y cómo quedaste, y lo
   reviso todos los meses."
5. **Precio con anclaje:** presentá los 3 tiers, señalá el Tier 2 como el recomendado.
6. **Cierre suave:** "¿Querés que lo hagamos? Firmamos un acuerdo simple, agendamos, y
   en [X días] estás blindado."

### Manejo de objeciones

- **"Ya tengo antivirus."** → "Perfecto, uso ese mismo (Defender) pero lo dejo a máxima
  potencia y blindado para que no lo puedan apagar — que es justo lo que hace el
  ransomware primero. La mayoría lo tiene a medias sin saberlo."
- **"Es caro."** → "Comparalo con lo que perdés un solo día sin poder facturar, o con
  recuperarte de un ataque: prevenir cuesta decenas de veces menos que recuperarse.
  Y si querés, arrancamos con el Tier básico."
- **"Nunca me pasó nada."** → "Es la frase que más escucho de los que después llaman
  cuando ya pasó. Los ataques hoy son automáticos, no eligen — barren negocios chicos
  justamente porque están desprotegidos."
- **"No entiendo de esto."** → "No hace falta. Por eso me contratás: yo lo hago y te lo
  explico en criollo con un informe claro."
- **"¿Y si me rompés algo?"** → "Por eso trabajo en modo observación primero: miro qué
  pasaría antes de activar cualquier bloqueo, y solo lo activo cuando confirmo que no
  afecta tu software. Cero improvisación."
- **"Mandame info por mail."** → "Te mando ahora mismo un resumen de una página y un
  informe de ejemplo. ¿Te llamo el [día] para ver si tiene sentido para tu caso?"
  (Y seguí — el "mandame mail" muere si no hay seguimiento agendado.)

---

## 7. Track paralelo freelance (para caja)

Mientras armás y vendés el servicio, tomá freelance para **cubrir gastos sin descarrilar
lo principal**. Regla: **máximo ~30–40% de tu tiempo** en freelance; el resto al negocio.
Si el freelance te come el Mes 2, no vas a vender. El freelance es el puente, no el destino.

### Plataformas (2026)

- **Toptal** — top ~3% del talento freelance, mejor pago, proyectos serios de Python/
  seguridad/automatización, clientes con presupuesto. Requiere pasar su screening, pero
  encaja con tu perfil. La mejor relación calidad/pago si entrás.
- **Upwork** — mayor volumen y variedad; podés conseguir gigs de Python y seguridad, con
  herramientas de tracking y gestión. Más competido en precio (hay quien cobra USD 10/h),
  así que posicioná por especialización, no por barato.
- **Arc.dev** — vetted freelance/full-time, Python/ML/full-stack; screening técnico.
- **Lemon.io** — bueno para startups que buscan devs Python/FastAPI/LLM pre-evaluados
  (encaja con tu stack de Jarvis).
- **Fiverr / Freelancer.com** — para tareas chicas y bien definidas; útil para arrancar
  reputación rápido, no para ingresos serios.

### Qué ofrecer (jugá a tus fortalezas, no compitas en commodity)

- **Automatización en Python** (scripts, integraciones, tooling) — tu terreno, buen pago.
- **Hardening de Windows / configuración de seguridad defensiva** — el mismo conocimiento
  del servicio, vendido por hora a quien ya sabe lo que quiere.
- **Consultoría/revisión de seguridad defensiva** (config review, no pentest ofensivo).
- Evitá gigs de pentesting ofensivo como freelance suelto: mismo límite legal/ético que
  en el producto — solo con autorización y alcance claro.

### Cuánto tiempo

Bloqueá franjas fijas (ej. 2 mañanas/semana) para freelance y **protegé el resto** para
prospección y entrega del servicio. Si un gig freelance amenaza con tapar el Mes 2,
rechazalo o posponelo: el objetivo del plan es el **ingreso recurrente del servicio**,
no maximizar horas freelance.

---

## 8. Track de evolución a PRODUCTO

Cada entrega manual es una **especificación de lo que Jarvis va a automatizar**. El
servicio no compite con el producto: lo **financia y lo define**. Camino: servicio
manual → servicio asistido por Jarvis → semi-producto → MSP/producto.

### Cómo cada paso del runbook se automatiza con Jarvis

- **Paso 0 (Defender full + Tamper)** → script/tool de Jarvis que verifica y aplica el
  estado deseado y lo reporta. (Ya hay base en `backend/app/malware/`.)
- **ASR / AppLocker / AMSI / Sysmon** → tools que aplican en **audit**, recolectan qué
  se habría bloqueado, y generan el diff para tu revisión antes de enforce. Automatiza
  la parte tediosa (recolección + reporte), vos seguís aprobando el enforce (gate).
- **Informe Antes/Después** → generación automática desde el estado capturado. Esto
  solo ya te ahorra horas por cliente y estandariza el entregable.
- **Monitoreo mensual (el abono)** → Jarvis corre la revisión periódica y arma el
  reporte; vos revisás excepciones. **Acá es donde el abono se vuelve escalable**: podés
  atender 20 clientes con el trabajo de atender 2.

> **Respetá los gates ya decididos del proyecto** (ver `CLAUDE.md` y el diseño): audit
> antes de block, enforce con aprobación, autorización por cliente. La automatización
> saca el trabajo repetitivo, **no** el criterio ni la autorización.

### Hitos

- **Mes 3:** el informe se genera solo desde el estado capturado. 4–6 clientes. Runbook
  100% documentado como SOP. Primeras tools de Jarvis para el Paso 0 y recolección de audit.
- **Mes 6:** el monitoreo mensual (abono) corre semi-automático con Jarvis; vos revisás
  excepciones. 8–15 clientes con abono. El ingreso recurrente cubre tus gastos base.
  Empezás a delegar entregas (contratar/tercerizar la ejecución rutinaria).
- **Mes 12:** semi-producto/MSP: onboarding estandarizado, panel por cliente, Jarvis hace
  la recolección + reporte + alertas y vos operás por excepción. Evaluás WDAC/WFP como
  tier premium. El servicio dejó de depender de tu tiempo hora a hora.

---

## 9. Métricas y checkpoints semanales

Medí **actividad comercial** (lo que controlás), no solo resultados (que llegan después).

### Métricas semanales

- **Contactos nuevos** (meta Mes 2: ≥ 20/semana en semanas de prospección).
- **Conversaciones de venta** (reuniones/llamadas reales).
- **Propuestas enviadas.**
- **Clientes cerrados** y **setup cobrado**.
- **Abonos activos** (el número que más importa a largo plazo).
- **Referidos pedidos / recibidos.**
- **Horas freelance** (que no supere el tope — señal de descarrilamiento si sube).

### Checkpoints

- **Fin de cada semana:** revisá el CSV de prospectos y las métricas. ¿Estás contactando
  suficiente? El error #1 es dejar de prospectar cuando entra un cliente.
- **Fin Semana 4 (fin Mes 1):** ¿producto empaquetado + proceso probado + materiales +
  lista? Gate para pasar a vender.
- **Fin Semana 6:** ¿primer cliente cerrado o al menos en entrega? Si no hay NINGUNA
  conversación de venta avanzada, revisá oferta/precio/segmento **antes** de seguir.
- **Fin Semana 8 (fin Mes 2):** ¿2–3 clientes, primer ingreso, abonos activos? Balance y
  plan del Mes 3.

### Señales de alarma

- Semana sin contactos nuevos → estás escondiéndote en lo técnico. Corregí ya.
- Todos dicen "sí, barato" → subí el precio.
- Todos se van al oír el precio → precio o segmento equivocado.
- Muchas charlas, cero cierres → falla el cierre o falta prueba social; reforzá testimonio.

---

## 10. Riesgos y mitigación

### Legales

- **Trabajar sin autorización = delito.** Nunca toques un sistema de un cliente sin
  **autorización escrita firmada** (cláusula en el contrato, §ANEXO C). Esto vale incluso
  para lo defensivo: estás modificando su sistema. Sin firma, no arrancás.
- **Nada ofensivo como servicio.** No vendas ni ejecutes pentesting/escaneo/explotación
  como producto. Si un cliente lo pide, es otro contrato, con otro alcance y otra
  autorización explícita — y ni siquiera es parte de este plan.
- **Datos del cliente.** Vas a ver información sensible. Cláusula de confidencialidad y
  manejo mínimo de datos. No copies ni saques datos del cliente de sus sistemas.
- **Revisión legal local.** La plantilla de contrato es un **borrador**: hacela revisar
  por un profesional en `Rosario` antes de usarla en serio. Impuestos y
  facturación también (registrate/facturá según tu régimen local).

### De alcance (scope creep)

- **Alcance fijo y por escrito.** El "¿ya que estás, me mirás la impresora?" mata el
  margen. Todo fuera del paquete es otro presupuesto. El contrato define exactamente qué
  entra.
- **Audit antes de block, siempre.** Riesgo técnico real: un enforce mal puesto rompe
  software legítimo del cliente. La regla del checklist (audit largo → verificar → block)
  es tu seguro. No la saltees por apuro.

### De sobreventa

- **No prometas invulnerabilidad.** Vendé **reducción de riesgo**, no "imposible que te
  hackeen". Prometer lo segundo es mentira y crea responsabilidad. Sé explícito en el
  informe y el contrato: reducís drásticamente la superficie de ataque; no la eliminás.
- **No prometas SOC 24/7 si no lo das.** Sos prevención + revisión periódica. Sé honesto
  sobre qué cubre el abono (revisión mensual, no vigilancia en vivo). Sobreprometer
  quema tu reputación en la primera falla.
- **No des fecha que no podés cumplir.** Las primeras entregas tardan más. Poné plazos
  con colchón.

### Del negocio

- **No vender.** El riesgo #1. Mitigación: el Mes 2 es 80% comercial por diseño; medí
  contactos, no código.
- **Depender de un solo cliente.** Meta 2–3 desde el arranque; abonos para ingreso
  diversificado.
- **Quemarte.** El freelance + servicio + producto es mucho. Protegé el foco: el abono
  recurrente es lo que te compra tiempo para respirar. Priorizalo.

---

# ANEXOS — Borradores usables

## ANEXO A — Copy de landing (borrador)

> Adaptá nombres, precios y ciudad. Reemplazá `{{...}}`.

---

**[Titular]**
Blindá las computadoras de tu {{negocio}} contra ransomware — sin comprar nada.

**[Subtítulo]**
El 60% de las PyMEs que sufren un ataque cierran en 6 meses. Dejo tu Windows en su
máxima potencia de defensa y blindado para que ni un virus lo pueda apagar. Usando las
herramientas que ya tenés. Precio fijo, sin sorpresas.

**[El problema]**
Los ataques ya no eligen: barren automáticamente negocios chicos porque están
desprotegidos. Y Windows viene con defensas potentes… a media máquina. La mayoría de
las PyMEs nunca las activó del todo.

**[Qué hago]**
Activo y blindo todas las capas de defensa nativas de Windows (antivirus a full +
protección anti-sabotaje, bloqueo de las cadenas de ataque más comunes, control de qué
software puede correr, detección de amenazas en memoria). Trabajo en modo observación
primero: nunca activo un bloqueo sin confirmar que no afecta tu software.

**[Qué recibís]**
Un informe claro de cómo estabas y cómo quedaste, y —si querés— una revisión mensual
para que siga protegido.

**[Planes]**
- **Básico** — {{precio}}: defensa esencial activada y blindada. Informe incluido.
- **Completo** ⭐ *(recomendado)* — {{precio}} setup + {{precio}}/mes: blindaje total +
  revisión mensual.
- **Gestionado** — {{precio}} setup + {{precio}}/mes: para negocios con más equipos o
  datos más sensibles.

**[Prueba]**
"{{testimonio}}" — {{cliente}}
[Ver informe de ejemplo →]

**[Llamado a la acción]**
Escribime y en una charla de 15 minutos te digo cómo está tu situación hoy.
[WhatsApp] · [Mail]

---

## ANEXO B — Mensajes de prospección (borradores)

### Versión CÁLIDA (red cercana)

> Hola {{nombre}}, ¿cómo andás? Te cuento algo que arranqué: ayudo a negocios chicos a
> blindar sus computadoras contra ransomware y virus, usando las defensas que Windows ya
> trae (sin comprar licencias). Me acordé de vos por [tu {{rubro}} / que manejás datos de
> clientes]. ¿Tenés 15 min esta semana para que te cuente y de paso te digo cómo estás
> parado hoy? Sin compromiso.

### Versión FRÍA (negocio local que no te conoce)

> Hola, buenas. Me presento: soy {{nombre}}, trabajo en seguridad informática para PyMEs
> de {{ciudad}}. Ayudo a estudios/consultorios/comercios a dejar sus computadoras
> blindadas contra ransomware, usando las defensas que Windows ya incluye — sin comprar
> nada nuevo. El 60% de las PyMEs que sufren un ataque cierran en 6 meses, y casi todas
> pensaban que "a mí no me va a pasar". ¿Le interesaría una revisión rápida y sin costo
> de cómo está hoy su seguridad? Con eso ya se lleva un diagnóstico claro, decida o no
> avanzar.

### Seguimiento (si no responden en ~3–4 días)

> Hola {{nombre}}, te reboto el mensaje por si se te pasó. Sin apuro — si te interesa,
> con una charla corta ya te dejo un panorama de cómo estás. ¿Te viene bien el {{día}}?

---

## ANEXO C — Contrato / autorización (borrador simple)

> ⚠️ **BORRADOR. No es asesoramiento legal.** Hacelo revisar por un profesional en
> `Rosario` antes de usarlo. Ajustá a tu régimen de facturación e
> impuestos y a la ley local de protección de datos.

---

**ACUERDO DE SERVICIOS DE SEGURIDAD DEFENSIVA**

**Entre:** {{Tu nombre / razón social}} ("el Proveedor") y {{Nombre del cliente / empresa}}
("el Cliente").
**Fecha:** {{fecha}}.

**1. Objeto.** El Proveedor prestará servicios de **seguridad defensiva** sobre los
sistemas Windows del Cliente, consistentes en la configuración y refuerzo (hardening) de
las capacidades de defensa nativas del sistema operativo, según el tier contratado.

**2. Alcance (tier {{1/2/3}}).** Incluye: {{listar del paquete — Defender + Tamper, ASR,
AppLocker, AMSI, Sysmon según tier}}. **No incluye:** pruebas de penetración ni ninguna
actividad ofensiva, soporte de IT general, ni ninguna tarea no listada arriba. Todo
trabajo fuera de este alcance requiere acuerdo por escrito adicional.

**3. AUTORIZACIÓN.** El Cliente **autoriza expresamente y por escrito** al Proveedor a
acceder y modificar la configuración de seguridad de los equipos identificados en el
Anexo de Equipos, **exclusivamente** con el fin descrito en este acuerdo. El Cliente
declara ser titular o tener facultad para autorizar el trabajo sobre dichos equipos.
**Sin esta autorización firmada, el Proveedor no realizará ninguna acción.** Esta
autorización no habilita ninguna actividad ofensiva ni acceso más allá de lo necesario
para el servicio defensivo contratado.

**4. Método y resguardo.** El Proveedor aplicará los controles de bloqueo primero en
**modo auditoría**, verificando que no afecten el software legítimo del Cliente, antes de
activarlos en modo bloqueo. El Cliente colaborará informando el software crítico para su
operación.

**5. Confidencialidad.** El Proveedor mantendrá confidencial toda información del Cliente
a la que acceda, no la copiará ni extraerá de los sistemas del Cliente salvo lo
estrictamente necesario para el servicio (p. ej. capturas para el informe, previa
anonimización cuando corresponda), y no la divulgará a terceros.

**6. Entregable.** Al finalizar el setup, el Proveedor entregará un **informe
Antes/Después** del estado de seguridad de los equipos.

**7. Precio y pago.** Setup (pago único): {{monto}}. Abono mensual (si aplica): {{monto}},
por {{revisión mensual de configuración, ajustes y reporte}}. Forma y plazo de pago:
{{acordar}}. Facturación según {{régimen local}}.

**8. Limitación de responsabilidad.** El servicio **reduce** el riesgo de seguridad; **no
garantiza** invulnerabilidad ni la imposibilidad de incidentes. El Proveedor no será
responsable por daños derivados de ataques, fallas o pérdidas de datos, salvo dolo o
negligencia grave. La responsabilidad total del Proveedor se limita al monto abonado por
el Cliente.

**9. Vigencia y baja.** El abono es mensual y puede darse de baja por cualquiera de las
partes con {{X días}} de aviso. El setup es un servicio de única vez ya prestado.

**10. Ley aplicable.** {{Jurisdicción de `Rosario`}}.

Firmas: _______________________ (Proveedor)   _______________________ (Cliente)

**Anexo de Equipos:** {{listar equipos autorizados — identificación, ubicación}}.

---

# 11. Ajuste Rosario/Argentina + arranque sin red

> Esta sección **sobrescribe** los supuestos de precio y de "arranque por red cercana"
> del resto del plan para tu caso real: **Rosario, Santa Fe, Argentina**, y **sin
> conocidos con negocios** (sin red cálida). Todo lo demás del plan (paquete, runbook,
> entregable, contrato, evolución a producto) sigue igual.

## 11.1 Localización de precios (contexto argentino 2026)

### Por qué esto cambia todo

Argentina tiene dos particularidades que rompen el pricing "de manual":

- **Inflación en pesos.** Un precio fijado en pesos hoy se licúa en meses. Un **abono
  mensual en pesos sin ajuste es una trampa**: cobrás cada vez menos en términos reales.
- **Brecha y estabilización.** Durante 2026 el tipo de cambio viene lateralizando con
  más estabilidad y —dato clave— el BCRA **eliminó el tope anual de USD 36.000** para
  exportadores de servicios y freelancers: podés recibir y **mantener dólares sin
  obligación de pesificar**. Esto favorece cotizar en USD.

**Conclusión operativa: cotizá en USD (o USD-linked) y cobrá/ajustá contra el dólar,
no contra el peso.**

### Cómo estructurar el precio en Rosario

1. **Setup:** fijalo en **USD** (número de referencia) y cobralo en pesos al **dólar
   MEP/financiero del día** (o en USD/cripto si el cliente puede). Así el número no se
   te licúa entre que cotizás y cobrás.
2. **Abono mensual:** dejalo **USD-linked**. En el contrato: "abono equivalente a USD X,
   facturado en pesos al tipo de cambio {MEP / referencia acordada} del día de emisión".
   Esto mantiene el valor real mes a mes sin renegociar. **Es la única forma de que el
   recurrente no se te derrita.**
3. **Ancla local, no global.** El dueño de una PyME rosarina no compara tu precio con
   un MSSP de EE.UU. (USD 2.000–5.000/mes): lo compara con lo que gasta en el "chico que
   le arregla las máquinas" o en su antivirus. Tu número tiene que sonar razonable
   contra *eso*, no contra el mercado yanqui.

### Rangos realistas para PyMEs de Rosario (ejemplo, ajustar)

Bastante **por debajo** de los rangos globales de §3, porque el poder adquisitivo local
es menor y estás construyendo tus primeros casos:

| Concepto | Tier 1 Básico | Tier 2 Completo | Tier 3 Gestionado |
|---|---|---|---|
| **Setup (USD, cobrado en $ al MEP)** | USD 80–180 | USD 200–450 | USD 450–900 |
| **Abono (USD-linked / mes)** | USD 0–20 | USD 30–70 | USD 70–150 |

> **Cómo llevarlo a pesos:** multiplicá el número USD por el **dólar MEP del día**
> (ej. si el Tier 2 setup son USD 300 y el MEP está a $X, cobrás 300 × $X en pesos).
> No uses el dólar oficial para cotizar (te deja corto); usá MEP o el financiero que
> manejes. Recalculá en cada factura. **Estos USD son ejemplos de estructura, no precios
> cerrados de Rosario** — validá con las primeras 3 charlas reales (test de las tres
> reacciones, §3).

### Sí pagan, aunque el presupuesto sea más ajustado

La PyME rosarina tiene menos margen que la de EE.UU., pero **paga por tranquilidad**
cuando el dolor es concreto — sobre todo las que manejan **datos de terceros y no pueden
frenar**: estudios contables (datos fiscales + deadlines de AFIP/ARCA), consultorios y
clínicas (datos de pacientes), estudios jurídicos y escribanías (confidencialidad).
Para estos, un ransomware no es "una molestia": es no poder cerrar un balance en
vencimiento o perder historias clínicas. Ahí el precio deja de ser el problema.

**Facturación:** para clientes locales, factura tipo A/B/C según tu condición (monotributo
suele alcanzar para arrancar). Para freelance del exterior (§11.3), **Factura E**.
Consultá un contador rosarino para el encuadre — te va a servir además como *primer
contacto del nicho* (ver 11.2).

## 11.2 Arranque de prospección SIN red cálida

El plan original arrancaba por conocidos. Vos no los tenés, así que **el Mes 2 se
reordena**: en vez de "red cercana → frío", es **nicho único → piloto → frío
especializado → boca a boca**. Esto reemplaza los Días 21–25 del plan.

### (a) Elegí UN nicho concreto: estudios contables de Rosario

No le vendas "a PyMEs" en general: **especializate en estudios contables**. Razones:

- **Densidad altísima** en Rosario (centro y Pichincha están llenos), así que el mercado
  te alcanza para años sin salir de la ciudad.
- **Datos sensibles + deadlines duros** (vencimientos impositivos) = dolor real y urgencia.
- **Se conocen entre ellos.** Un nicho denso y conectado hace que el **boca a boca**
  funcione: un contador satisfecho te recomienda a tres colegas. Con red cálida cero,
  el boca a boca dentro de un nicho es tu sustituto de la red.
- **Mensaje afiladísimo.** "Blindo las computadoras de estudios contables contra
  ransomware, sin que compren nada" pega mucho más que un mensaje genérico.

Especializarte también te deja **estandarizar el runbook** para el software típico del
rubro (Tango, Bejerman, SIAp/aplicativos ARCA, Office) — menos sorpresas en el enforce.

### (b) Conseguí el PRIMER caso con 1 PILOTO gratis o casi gratis

Sin testimonios, nadie te compra. Rompé el huevo y la gallina con **un piloto**:

- Ofrecé a **un** estudio contable el blindaje **gratis o casi** (ej. solo cobrás un
  simbólico o nada) **a cambio de:** (1) un **testimonio** por escrito/video, (2)
  permiso para usarlo como **caso** (anonimizado si prefiere), y (3) **2–3 referidos** a
  colegas si queda conforme.
- **Igual firmás el contrato + autorización** (Anexo C), aunque sea gratis. El piloto es
  gratis; la seriedad y el resguardo legal, no.
- Es **una sola** PyME, no diez. El objetivo es tu primer informe real "en el rubro" y
  la primera voz que te recomienda.

**Cómo conseguir esa primera puerta sin conocidos:**

- **Visita en persona.** Rosario es una ciudad donde tocar el timbre de un estudio y
  hablar con el dueño funciona. Llevá una hoja (el informe de muestra) y pedí 10 minutos.
- **Tu propio contador / el que consultes para facturar** (11.1): es tu primer contacto
  natural del nicho. Empezá por ahí.
- **Colegios y cámaras profesionales** (ver punto d) — asistí a un evento, conseguí
  contactos.
- **LinkedIn local:** buscá "contador Rosario", conectá, mensaje directo (guion abajo).
- **Grupos locales:** grupos de comerciantes/profesionales de Rosario en WhatsApp/
  Facebook, foros de emprendedores de la ciudad.

### (c) Guion de contacto en frío — Rosario / estudios contables

**En persona (recepción de un estudio):**

> Buenas, ¿cómo está? Soy {{nombre}}, trabajo en seguridad informática acá en Rosario,
> especializado en estudios contables. Paso porque ustedes manejan datos fiscales de un
> montón de clientes y hoy el 60% de las PyMEs que sufren un ransomware terminan
> cerrando. Dejo las computadoras blindadas usando las defensas que Windows ya trae —sin
> que compren nada— y les entrego un informe claro. ¿Tendría 10 minutos el titular esta
> semana para que le muestre cómo están parados hoy, sin costo?

**LinkedIn / mail frío a un contador:**

> Hola {{nombre}}, soy {{tunombre}}, de Rosario. Ayudo a estudios contables a blindar
> sus PCs contra ransomware usando las defensas nativas de Windows (sin comprar
> licencias). Lo menciono porque un estudio maneja datos fiscales de muchos clientes y
> un ataque en pleno vencimiento es un problema serio. Estoy tomando **un estudio como
> caso piloto sin costo** a cambio de un testimonio. ¿Te interesaría una revisión rápida
> y gratuita de cómo está hoy tu seguridad? Con eso te llevás un diagnóstico, decidas o
> no avanzar.

**Seguimiento (3–4 días):** igual que el Anexo B, tono corto y sin apuro.

### (d) Cámaras y asociaciones profesionales de Rosario como canal

Un solo canal institucional te da acceso a decenas de prospectos del nicho de golpe.
Apuntá a instituciones de Rosario/Santa Fe como (verificá nombres y membresía actual):

- **Consejo Profesional de Ciencias Económicas de Santa Fe (Cámara II – Rosario)** — el
  colegio de los contadores; eventos, capacitaciones, boletines. Ofrecé una **charla
  gratuita** "cómo proteger tu estudio del ransomware": te posiciona como experto ante
  la sala entera.
- **Bolsa de Comercio de Rosario** y su ecosistema PyME.
- **Federación Gremial / cámaras de comercio y de la pequeña empresa** de Rosario.
- **Polo Tecnológico Rosario** y comunidades tech locales (para el track freelance y
  para networking).

Táctica de canal: no vendas de entrada, **ofrecé valor** (una charla, una checklist
gratuita "5 cosas que tu estudio debería tener activadas"). El que da una charla en el
Consejo no persigue clientes: los clientes lo llaman a él.

### Reemplazo concreto de los Días 21–25 (Mes 2)

- **Día 21:** armá la lista de 30–40 estudios contables de Rosario (Google Maps zona
  centro/Pichincha + LinkedIn "contador Rosario"). Contactá a tu contador para el piloto.
- **Día 22:** primeras 10 puertas frías (en persona o LinkedIn) con el guion de arriba.
  Contactá al Consejo Profesional para ofrecer una charla.
- **Día 23:** cerrá **el estudio piloto**. Firmá contrato+autorización (gratis pero formal).
- **Día 24:** 10 contactos fríos más. Preparás la entrega del piloto.
- **Día 25:** entregás el piloto (arranca el runbook) — este es tu primer caso real. El
  resto del Mes 2 sigue igual, pero ahora **con testimonio y caso del nicho** para cerrar
  los pagos.

## 11.3 Freelance en USD como palanca de caja rápida (probablemente tu PRIMER ingreso)

Para alguien **sin red local**, el cliente rosarino tarda en llegar; el **freelance
remoto en dólares puede darte plata antes**. Y por el tipo de cambio, **una hora
cobrada en USD rinde muchísimo más en pesos** que el trabajo local. Esto no depende de
conocer a nadie en Rosario: dependés de tu skill (Python/seguridad), que ya tenés.

**Por eso, para tu caso, el orden se invierte respecto del §7:** el freelance-USD deja
de ser "un extra para gastos" y pasa a ser **el motor de caja del arranque**, mientras
construís en paralelo el servicio local recurrente. El servicio local es el destino
(recurrente, escalable, tu producto); el freelance-USD es cómo te bancás el viaje.

### Qué plataformas sirven desde Argentina

- **Toptal** — la de mejor pago; top ~3%. Si pasás el screening, proyectos serios de
  Python/automatización/seguridad con clientes de presupuesto en USD. La mejor relación
  esfuerzo/retorno para tu perfil.
- **Upwork** — mayor volumen; posicionate por especialización (automatización Python,
  hardening Windows, revisión de seguridad defensiva), no por precio.
- **Arc.dev / Lemon.io** — vetted, orientadas a startups (FastAPI/LLM encaja con tu
  stack de Jarvis). Buen puente entre "marketplace" y "empleo remoto".
- **Contra / Gun.io / Wellfound** — trabajo remoto directo con empresas del exterior.
- **LinkedIn** — buscar "remote Python contractor / security" y aplicar directo también
  funciona sin plataforma intermediaria.

Ofrecé lo mismo que te hace fuerte: **automatización en Python, hardening/config de
seguridad defensiva de Windows, revisión de seguridad** (defensivo — **nada de pentest
ofensivo suelto**, mismo límite que el producto).

### Cómo cobrar del exterior (2026, en regla)

- **Payoneer** — el más aceptado por plataformas freelance globales; retiro con comisión
  de hasta ~2%. Estándar de la industria.
- **Deel** — ideal para **relaciones estables** con una empresa del exterior (contratos
  recurrentes); maneja el contrato y el pago.
- **Wise** — bueno para transferencias directas de clientes; buen tipo de cambio.
- **Marco fiscal:** por servicios al exterior emitís **Factura E**. El BCRA **eliminó el
  tope de USD 36.000** anual y **podés mantener los dólares sin pesificar** (desde sept.
  2025 los bancos locales no pueden cobrar comisión por recibir estas transferencias de
  exportación de servicios). Encuadre con contador (monotributo suele alcanzar para
  empezar) — otra vez, tu contador es también prospecto del nicho.

### Cómo balancear freelance-USD (caja ya) con servicio local (recurrente)

- **Fase 1 (Mes 1–2):** el freelance-USD es tu **caja principal**. Dedicale la franja
  necesaria para cubrir gastos, pero **blindá tiempo diario para el servicio local**
  (armar en Mes 1; piloto + prospección de estudios en Mes 2). Regla mínima: **al menos
  1 acción comercial local por día**, aunque el grueso de las horas sea freelance.
- **Fase 2 (Mes 3–6):** a medida que entran abonos locales (recurrente en USD-linked),
  **bajá gradualmente las horas de freelance**. El freelance es caja lineal (dejás de
  trabajar, dejás de cobrar); el abono es caja recurrente. Migrá de uno al otro.
- **Señal de descarrilamiento:** si una semana no hiciste **ninguna** acción del servicio
  local porque el freelance te tapó, corregí. El freelance no puede comerse el proyecto:
  es el medio, no el fin.
- **Meta cruzada:** que el freelance-USD te compre la **estabilidad mental** para no
  cerrar mal el primer cliente local por necesidad de plata. Vender desde la urgencia
  es vender barato.

---

## Fuentes

- [SOC as a Service Pricing in 2026 — BD Emerson](https://www.bdemerson.com/article/soc-as-a-service-pricing)
- [How Much Do Managed Security Services Cost in 2026? — Meriplex](https://meriplex.com/managed-security-services-cost-2026/)
- [Managed Security Services for Small Business in 2026 — Defend My Business](https://defendmybusiness.com/managed-security-services-small-business-2026/)
- [Pricing Managed Security Services (MSSP) Guide for 2026 — Bennett Financials](https://bennettfinancials.com/pricing-managed-security-services/)
- [MSSP Pricing 2026: Costs, Models and Tips — MSSPProviders.io](https://msspproviders.io/resources/how-much-does-an-mssp-cost/)
- [MDR Vendor Pricing Comparison: What SMBs Pay in 2026 — Bellator Cyber](https://bellatorcyber.com/blog/mdr-vendor-pricing-comparison)
- [MSP Pricing Models: 2026 Playbook — Flamingo](https://www.flamingo.run/blog/msp-pricing-models)
- [The Productized Service Guide — ManyRequests](https://www.manyrequests.com/blog/productized-service-guide)
- [The Complete Guide To Productized Services (2026) — Assembly](https://assembly.com/blog/productized-services)
- [Productized Services in 2026: 7 Trends — ProductizeHub](https://productizehub.com/blog/productized-services-2026-trends)
- [How to Price a Productized Service — Botensten](https://botensten.com/articles/how-to-price-a-productized-service)
- [11 Best Freelance Cybersecurity Developers — Toptal](https://www.toptal.com/developers/cybersecurity)
- [Best Freelance Python Developers for Hire — Upwork](https://www.upwork.com/hire/python-developers/)
- [Best Freelance Cybersecurity Developers — Arc.dev](https://arc.dev/hire-developers/cybersecurity)
- [Cybersecurity Services Agreement Template — ClickUp](https://clickup.com/p/templates/service-agreement/cybersecurity-services-agreement-template)
- [Cybersecurity Contractual Clauses — SES](https://www.ses.com/sites/default/files/2023-10/SES-Cyber-Security-Contractual-Clauses-fv1-Sept23.pdf)
- [Small Business Cybersecurity Statistics 2026 — SQ Magazine](https://sqmagazine.co.uk/small-business-cybersecurity-statistics/)
- [60 Small Business Cybersecurity Statistics 2026 — Spacelift](https://spacelift.io/blog/small-business-cybersecurity-statistics)
- [Ransomware in 2026: Why Small Businesses Remain the #1 Target — Entre](https://www.entremt.com/ransomware-in-2026-why-small-businesses-remain-the-1-target/)
- [Deel, Payoneer y Wise: cobrar del exterior en regla 2026 — Conta Online](https://www.contaonline.com.ar/blog/deel-payoneer-wise-cobrar-exterior-argentina-2026)
- [Payoneer Argentina 2026: guía completa para cobrar del exterior — Saldo](https://blog.saldo.com.ar/guia-payoneer-argentina-2026/)
- [Eliminación de restricciones cambiarias impulsa exportación de servicios y trabajo remoto — Infobae](https://www.infobae.com/economia/2026/02/22/la-eliminacion-de-las-restricciones-cambiarias-impulsa-la-exportacion-de-servicios-y-el-trabajo-remoto/)
- [Trabajos remotos en dólares para argentinos — Guía 2026 — Global66](https://www.global66.com/blog/trabajos-remotos-en-el-extranjero-desde-argentina/)
