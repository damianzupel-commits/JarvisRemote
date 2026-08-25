# Exoesqueletos de aumento y asistencia: fundamentos y factibilidad real

> Informe de investigación técnica. Estado del arte a agosto de 2026, con datos y
> fuentes reales. Marco: tecnología **asistiva y de aumento** (soporte de carga,
> movilidad, economía de esfuerzo) — el mismo campo de los exos industriales y
> médicos. No cubre armamento.
>
> Autor del pedido: Damian (desarrollador, construye el asistente "Jarvis").
> Objetivo del documento: entender si un individuo o equipo chico puede aspirar a
> construir un exoesqueleto real de forma progresiva, y dónde encaja de verdad una
> capa de IA/control como Jarvis.

---

## 0. TL;DR (resumen ejecutivo honesto)

- **Estado del arte en una línea:** los exoesqueletos reales de 2026 no dan
  "super fuerza de película"; lo que sí hacen —y está probado— es **transferir
  carga al suelo/estructura** (espalda y hombros en industria) y **reducir el
  costo metabólico** de caminar/correr entre ~10% y ~25% con asistencia bien
  sintonizada en articulaciones puntuales (tobillo, cadera). El único full-body
  motorizado que amplificaba fuerza ~20× (Sarcos Guardian XO) nunca se
  comercializó a escala.
- **Los dos cuellos de botella que mandan sobre todo lo demás:** (1) **energía**
  —la densidad de batería (150–250 Wh/kg) limita autonomía y potencia; cargás una
  batería para poder cargar la batería— y (2) **control en tiempo real**
  —estimar la *intención* del usuario y entregar el torque correcto en el
  instante correcto, sin latencia que desincronice al humano de la máquina.
- **Escalera de factibilidad:** (1) exo **pasivo** de espalda → muy alcanzable,
  incluso DIY. (2) Asistencia **motorizada de una articulación** (tobillo o
  cadera) → proyecto serio pero abordable con electrónica moderna. (3) Aumento
  **multi-articulación** de fuerza/velocidad → grado industrial/investigación,
  fuera de alcance para una persona sola.
- **Primer proyecto recomendado:** un **exosuit pasivo de espalda** (bandas
  elásticas, sin motores) — probadamente reduce la actividad muscular del erector
  de la columna 15–45%, cuesta poco, no puede lesionarte por falla de software, y
  te enseña el 80% de los problemas de acople humano-máquina antes de meter un
  solo motor.

---

## 1. Estado del arte 2026: qué logran de verdad los sistemas reales

Conviene separar dos ejes que se confunden todo el tiempo:

- **Pasivo vs. activo.** Un exo **pasivo** no tiene motores: usa resortes,
  elásticos o mecanismos de barra para almacenar y devolver energía o para
  redirigir carga hacia una estructura. Un exo **activo** tiene actuadores
  motorizados que *inyectan* energía y por lo tanto puede hacer trabajo neto
  positivo (pero necesita batería, control y trae riesgos nuevos).
- **Aumento (augmentation) vs. asistencia médica.** Aumentar a una persona sana
  (industria, milicia) vs. suplir función perdida (rehabilitación, movilidad).

### 1.1 Full-body motorizado de amplificación de fuerza — el caso Sarcos Guardian XO

El **Sarcos Guardian XO** es el ejemplo de "traje de fuerza" más completo que
llegó a existir: full-body de **24 grados de libertad**, que según el fabricante
amplifica la fuerza hasta **20×**, con carga útil máxima de **90 kg (200 lb)** de
modo que el operador siente que levanta ~4,5 kg. Dato clave de ingeniería:
lograron bajar el consumo eléctrico a **menos de 400 W** (dos baterías de ion-litio,
"como un televisor LED grande"), con **baterías hot-swap de ~2 h** cada una para
cubrir un turno. ([IEEE Spectrum](https://spectrum.ieee.org/sarcos-guardian-xo-powered-exoskeleton),
[New Atlas](https://newatlas.com/sarcos-robotics-guardian-xo-exoskeleton/57847/),
[The Robot Report](https://www.therobotreport.com/rbr50-company/sarcos-robotics-commercializes-guardian-xo-full-body-exoskeleton-for-industrial-use/))

La lección honesta: incluso con financiamiento de nivel corporativo, un full-body
que amplifica fuerza es tan caro, complejo y difícil de rentabilizar que **no se
volvió un producto de volumen**. Que algo se demuestre en video no significa que
sea viable de fabricar, mantener y usar en el mundo real.

### 1.2 Exos de piernas motorizados de una/dos articulaciones (asistencia, no super-fuerza)

- **Lockheed Martin ONYX** (versión militar de la tecnología *Dermoskeleton* de
  B-Temia): exo de **cuerpo inferior** con **actuadores electromecánicos de
  rodilla**, sensores e IA que aprende el movimiento del usuario y entrega
  "el torque correcto en el momento correcto" para subir pendientes o cargar
  peso. Pesa **menos de ~6,4 kg (14 lb)**. Un estudio independiente de la
  Universidad de Michigan mostró que los usuarios **gastaban menos energía** al
  subir una pendiente con mochila de ~18 kg. El feedback de campo (10th Mountain
  Division, Fort Drum) pidió baterías mil-spec, mejor ergonomía y **actuadores más
  rápidos con más torque** — un recordatorio de lo difícil que es el control fino.
  ([Breaking Defense](https://breakingdefense.com/2019/10/knees-of-iron-lockheeds-onyx-exoskeleton/),
  [Lockheed Martin](https://news.lockheedmartin.com/2018-11-29-Lockheed-Martin-Secures-U-S-Army-Exoskeleton-Development-Agreement))
- **HULC** (Human Universal Load Carrier, el predecesor hidráulico) quedó como
  historia; el linaje comercial de estos equipos evolucionó hacia dispositivos
  más livianos y específicos.

### 1.3 Exos industriales de espalda y hombros (el segmento más maduro y real)

Este es el nicho donde los exos **funcionan de verdad hoy** y se venden.

- **German Bionic Apogee / Apogee Ultra** (activo, lumbar): brinda hasta
  **36 kg (80 lb)** de soporte al levantar; una carga de ~32 kg "se siente" como
  9–11 lb en la zona lumbar. La versión Ultra agrega **soporte activo a la
  marcha** (10 millas se sienten como 8) y usa ML para adaptarse al usuario.
  ([Engadget](https://www.engadget.com/wearables/german-bionics-new-apogee-ultra-exoskeleton-can-lift-up-to-80-pounds-and-help-with-walking-140031689.html),
  [The Robot Report](https://www.therobotreport.com/german-bionic-debuts-apogee-powered-exoskeleton/))
- **HeroWear Apex / Apex 2** (pasivo, lumbar): **1,55 kg**, sin motores ni
  electrónica. Bandas elásticas que redirigen parte de la fuerza del lifting
  fuera de los músculos de la espalda. El prototipo redujo la actividad del
  **erector de la columna 23–43%** en tareas de inclinación y **14–16%** al
  levantar; el Apex 2 reporta hasta **40%** menos fatiga/esfuerzo por lifting.
  Es el mejor ejemplo de cuánto se logra **sin un solo motor**.
  ([Exoskeleton Report](https://exoskeletonreport.com/2023/03/herowear-introduces-apex-2-the-next-generation-of-exosuits-for-reducing-back-injuries/),
  [ScienceDirect – evaluación Apex](https://www.sciencedirect.com/science/article/abs/pii/S0021929021003912))
- **SuitX (ahora parte de Ottobock)** y otros fabrican exos modulares pasivos de
  espalda, hombros y piernas para líneas de montaje.

### 1.4 Rehabilitación y movilidad médica

- **Ekso Bionics — EksoNR**: exo de marcha para rehabilitación (ACV, lesión
  medular, daño cerebral adquirido; FDA-cleared). **~25 kg** autosoportado,
  **cuatro motores**, batería de ~4 h para ~12 km, control por pantalla táctil y
  feedback de marcha en tiempo real. Nota importante: **el paciente no carga el
  peso del equipo** —es autosoportado— lo cual es un principio de diseño que vale
  la pena copiar en prototipos.
  ([Ekso Bionics](https://eksobionics.com/eksonr/),
  [Rehacare](https://www.rehacare.com/en/media-news/emag/business/exoskeleton-rehabilitation))

### 1.5 Exos de investigación de tobillo/cadera (donde vive la mejor ciencia)

- **Stanford Biomechatronics (Collins/Slade)** — *"Personalizing exoskeleton
  assistance while walking in the real world"*, **Nature 610, 277–282 (2022)**:
  un exo de tobillo portátil, con **optimización human-in-the-loop** hecha
  **al aire libre** con sensores wearables, aumentó la **velocidad
  autoseleccionada 9 ± 4%**, redujo la **energía por distancia 17 ± 5%** vs.
  zapatillas normales, y bajó el **costo metabólico 23 ± 8%** caminando a
  1,5 m/s en cinta. La optimización fue **4× más rápida** que en laboratorio.
  ([Nature](https://www.nature.com/articles/s41586-022-05191-1),
  [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9556303/))
- **Harvard Biodesign / Wyss (Walsh)** — exosuits *blandos* (textiles + cables):
  asistencia de flexión de cadera reduce el costo metabólico de **caminar hasta
  15,2 ± 2,6%** (tethered) o **7,2 ± 2,9%** (portátil, 2,31 kg); asistencia de
  extensión de cadera, **17,4 ± 3,2%** (tethered) y **9,3%** (portátil a 1,5 m/s).
  Corriendo: exosuit tethered reduce el costo metabólico ~**5,4%** y el portátil
  ~**4,0%** a 2,5 m/s.
  ([Harvard Biodesign](https://biodesign.seas.harvard.edu/soft-exosuits),
  [Science Robotics – running exosuit](https://www.science.org/doi/10.1126/scirobotics.aan6708))

**Síntesis del estado del arte:** lo demostrado y repetible es (a) transferir
carga (industria/milicia) y (b) reducir el **costo energético** de la locomoción
en un rango de ~10–25% con asistencia de **una articulación** bien sintonizada.
Lo que sigue siendo demo cara y no-producto es la amplificación de fuerza
full-body.

---

## 2. Los subsistemas y su física/ingeniería

Un exo activo es siempre la misma cadena: **sensar → estimar intención →
computar torque → actuar → transmitir la fuerza al cuerpo**. Cada eslabón tiene
su física y sus trade-offs.

### 2.1 Actuadores: de dónde sale el torque

El requerimiento nace de la biomecánica. En la marcha humana, articulaciones como
tobillo y cadera generan **picos del orden de 1–1,5 N·m por kg de masa corporal**
(o sea ~70–120 N·m en un adulto) en fracciones de segundo. Ese es el número que
tenés que igualar (o una fracción, si sólo asistís).

- **Motores eléctricos BLDC (brushless):** el estándar actual. Alta densidad de
  torque, controlables con precisión (FOC), reversibles. Problema: el torque
  crudo de un motor chico es bajo, así que necesitás **reducción por engranajes**.
- **El dilema de la caja reductora:** más reducción = más torque pero **menos
  backdrivability** (el motor se vuelve "duro" de mover a mano) y aparece
  backlash/fricción. Poco reductor = suave y transparente pero poco torque.
- **Quasi-Direct-Drive (QDD):** BLDC de alto torque + reducción planetaria baja
  (5:1–10:1). Es el compromiso moderno: buena densidad de torque **y**
  backdrivability. Habilitado por los motores de dron de alta densidad de torque.
- **Series Elastic Actuators (SEA):** ponen un **resorte en serie** entre el
  motor y la carga. Medir la deflexión del resorte = medir la fuerza directamente,
  lo que da **control de torque de alta fidelidad**, absorbe impactos y protege al
  usuario y al reductor. Es de facto el enfoque preferido en robótica wearable,
  a costa de agregar masa y complejidad y de bajar el ancho de banda de control.
  ([Cambridge – SEA knee exo](https://www.cambridge.org/core/journals/wearable-technologies/article/serieselastic-actuator-with-two-degreeoffreedom-pid-control-improves-torque-control-in-a-powered-knee-exoskeleton/FBEBF3966808F9AC51138792D3B6BF10),
  [Actuator deep dive](https://www.wasilzafar.com/pages/series/sensors-actuators/sensors-actuators-actuator-robotic-joint.html))
- **Hidráulicos:** enorme densidad de fuerza (por eso HULC/Guardian los usaron)
  pero traen bomba, mangueras, fugas, ruido y complejidad. Poco amigables para DIY.
- **Neumáticos / músculos de McKibben:** livianos y "compliant" por naturaleza,
  buenos para exosuits blandos, pero difíciles de controlar con precisión y
  necesitan compresor/tanque.

**Trade-off central:** torque ↔ backdrivability ↔ masa ↔ controlabilidad. No
existe el actuador perfecto; elegís según la articulación y el objetivo.

### 2.2 Energía: el verdadero cuello de botella

Este es el muro contra el que choca todo exo activo.

- La batería de ion-litio ofrece **~150–250 Wh/kg**. Es un orden de magnitud
  menos densa que el combustible fósil y no mejora rápido. En la práctica, un exo
  activo portátil da **2–8 h** de operación y **la batería pesa**, lo que a su vez
  demanda más potencia para cargarla: un círculo vicioso.
- Por eso el logro de Sarcos de bajar a **<400 W** fue tan comentado, y por eso
  German Bionic y otros priorizan asistencia lumbar puntual en vez de mover todo
  el cuerpo: menos trabajo neto = menos vatios = menos batería = menos peso.
- Consecuencia de diseño: **la potencia limita todo**. Cuanto más querés
  "aumentar" (más torque, más articulaciones, más velocidad), más potencia y más
  batería necesitás, y más pesado y torpe se vuelve el sistema. Por eso los mejores
  resultados de investigación vienen de exos **tethered** (motores fuera del
  cuerpo, energía por cable): sacan el problema de la energía de la ecuación para
  estudiar el control puro.
  ([Reporte energía exos](https://eureka.patsnap.com/report-harness-renewable-energy-sources-for-exoskeleton-power))

### 2.3 Sensado y control: el cerebro en tiempo real

Aquí es donde una capa de IA aporta de verdad, pero también donde está el segundo
gran cuello de botella.

- **Sensores:**
  - **IMU** (acelerómetro + giróscopo): estiman fase de la marcha, ángulos y
    orientación de segmentos. Baratos y robustos; base de casi todo control.
  - **Sensores de fuerza/torque** (celdas de carga, deflexión del SEA, presión
    plantar): miden la interacción real humano-exo.
  - **EMG** (electromiografía de superficie): lee la señal eléctrica del músculo.
    Su valor es la **anticipación**: por el *delay electromecánico*, la señal EMG
    aparece **~50–100 ms antes** de que el músculo genere fuerza, así que en
    teoría podés detectar la intención antes del movimiento.
- **El problema del tiempo real:** el humano tolera muy poca latencia. Si el exo
  responde tarde, el usuario compensa con otro input y aparecen inestabilidades.
  Sistemas reales apuntan a lazos de control del orden de **~0,1 s** o menos entre
  señal y respuesta del motor. El EMG, además, es **no estacionario** y varía
  mucho entre personas y entre sesiones, así que exige calibración por usuario y
  se ensucia con el sudor, el movimiento del electrodo, etc.
  ([Review onset EMG](https://link.springer.com/article/10.1186/s12984-023-01268-8),
  [Myoelectric control review](https://pmc.ncbi.nlm.nih.gov/articles/PMC9655258/))
- **Qué significa "mejorar los reflejos" en términos reales:** no es acelerar tu
  sistema nervioso. Es **asistencia predictiva**: estimar tu intención de
  movimiento (de IMU/EMG/patrón de marcha) y entregar torque *sincronizado* con
  tu propio gesto, de modo que el esfuerzo neto baje. El exo no piensa por vos;
  se **anticipa** dentro de la ventana del delay electromecánico y del ciclo de
  marcha, que es cíclico y por lo tanto predecible. Ese es todo el "superpoder"
  realista: economía de esfuerzo y timing, no velocidad de reacción sobrehumana.

### 2.4 Estructura y acople humano-máquina: donde se lesiona la gente

El eslabón más subestimado. Un actuador perfecto conectado mal al cuerpo es
peligroso.

- **Grados de libertad (DOF) y alineación de ejes:** tus articulaciones no son
  bisagras simples (la rodilla rueda y desliza; el hombro es casi esférico). Si el
  eje del exo **no coincide** con tu eje anatómico, en cada movimiento aparecen
  fuerzas de cizalla y micro-desplazamientos que rozan, pinzan y a la larga
  **lesionan**. Por eso los exos serios agregan DOF pasivos de auto-alineación.
- **Transmisión de fuerza a tejidos blandos:** la carga entra por brazaletes/
  correas sobre músculo y piel, no sobre hueso. Presión mal distribuida = puntos
  de presión, isquemia, dolor. Los exosuits blandos reparten sobre áreas grandes;
  los rígidos necesitan interfaces bien acolchadas y ajustables.
- **Masa y su ubicación:** peso lejos del centro del cuerpo (sobre todo distal, en
  pies/manos) **penaliza** el costo metabólico —podés terminar gastando más
  energía por cargar el propio exo. Regla de oro: masa mínima y lo más proximal
  posible.

---

## 3. La escalera de factibilidad (de lo más alcanzable a lo menos)

Pensada para construir **de a poco**, cada peldaño enseñando lo necesario para el
siguiente.

### Peldaño 1 — Exo PASIVO de soporte de carga (espalda/hombros). MUY alcanzable, DIY real.

- **Qué es:** un arnés con **bandas elásticas** (o resortes/mecanismo de barras)
  que redirige parte de la carga de la espalda baja hacia caderas/muslos al
  inclinarte, o que soporta los brazos elevados para trabajo por encima de la
  cabeza. Sin motores, sin batería, sin software crítico.
- **Qué logra de verdad:** el HeroWear Apex (1,55 kg) reduce la actividad del
  erector de la columna **15–45%**. Eso es un resultado clínico-ergonómico serio,
  logrado **sin electrónica**.
- **Qué tan DIY es:** altamente. El diseño es mecánico y textil: patrones de
  arnés, puntos de anclaje, selección de la constante elástica, ruteo de las
  bandas para que asistan al flexionar y no al pararte derecho. Herramientas:
  costura técnica, impresión 3D para clips/anclajes, medición con una balanza/
  dinamómetro. El riesgo de lesión es bajo y **no depende de que un software no
  falle**.
- **Por qué empezar acá:** te enseña el problema #1 (acople humano-máquina y
  transmisión de fuerzas) sin ningún riesgo de un motor descontrolado.

### Peldaño 2 — Asistencia MOTORIZADA de UNA articulación (tobillo o cadera). Proyecto serio pero abordable.

- **Qué es:** un actuador (BLDC + reductor bajo, idealmente QDD o un SEA simple)
  en **una** articulación, controlado por un microcontrolador que lee una IMU y/o
  celda de carga, detecta la fase de marcha y entrega un pulso de torque
  sincronizado.
- **Dificultad:** salto grande respecto al peldaño 1. Ahora tenés electrónica de
  potencia, control de motor (FOC), un lazo de control en tiempo real, batería y
  —crítico— **seguridad**: límites de torque, paradas de emergencia,
  backdrivability para que si el software muere el usuario pueda mover la pierna.
- **Qué necesitás:** motor de dron/robótica de alta densidad de torque, driver
  con FOC (ODrive, moteus, SimpleFOC), IMU, microcontrolador de tiempo real,
  celda de carga, batería LiPo con BMS, y estructura impresa/mecanizada bien
  alineada. La comunidad *open-source* de robótica (OpenSEA, actuadores QDD
  estilo MIT Mini-Cheetah, etc.) hace esto **posible para un individuo** hoy.
- **Objetivo realista del peldaño:** **reducir el costo metabólico** de caminar/
  correr o asistir a subir escaleras — exactamente lo que demostraron Harvard y
  Stanford con **una** articulación. No apuntes a "super fuerza".

### Peldaño 3 — Aumento MULTI-articulación de fuerza/velocidad. Grado industrial/investigación.

- **Por qué es tan difícil:** el problema **no** escala linealmente. Coordinar
  cadera+rodilla+tobillo (y quizás tronco/brazos) implica: potencia que
  multiplica el problema de energía; control multi-DOF acoplado y estable en
  tiempo real; alineación anatómica en varias articulaciones a la vez; y una
  superficie de fallos enorme donde **cualquier** actuador que empuje en el
  momento equivocado puede tirarte o lesionarte. Es exactamente el territorio
  donde Sarcos gastó fortunas y aun así no llegó a producto.
- **Veredicto:** fuera de alcance para una persona o equipo chico sin una
  organización, presupuesto y equipo multidisciplinario detrás.

### El caso especial de "correr más rápido"

Spoiler honesto respaldado por evidencia:

- **Lo demostrado y sólido: reducir el costo metabólico**, es decir correr/caminar
  **más económicamente** (mismo ritmo, menos energía; o más lejos con la misma
  energía). Números reales: 23% en marcha (Stanford, Nature 2022), 4–5% corriendo
  (Harvard). Eso es real y repetible.
- **Multiplicar la velocidad máxima es muy difícil.** Hay trabajo teórico y
  prototipos de exos **pasivos tipo catapulta** que *calculan* velocidades de
  hasta ~20,9 m/s (~75 km/h) o sugieren correr **50% más rápido sin energía
  externa** aprovechando resortes — pero son **modelos y prototipos tempranos**,
  no algo que puedas ponerte y salir a correr al doble. En asistencia de sprint
  motorizada real, las mejoras medidas son modestas (del orden de fracciones de
  segundo en una distancia corta).
- **Por qué:** correr rápido no está limitado sólo por la fuerza de tus músculos,
  sino por **cuán rápido podés aplicar fuerza contra el suelo** en el brevísimo
  tiempo de contacto del pie. Un actuador tiene que ser increíblemente potente y
  rápido para ayudar en esa ventana sin desincronizarse de tu paso, y toda esa
  potencia vuelve a chocar con el muro de la energía.
  ([ScienceAlert – catapulta 50%](https://www.sciencealert.com/using-a-catapult-like-exoskeleton-could-get-us-running-50-percent-faster),
  [PubMed – "run 50% faster"](https://pubmed.ncbi.nlm.nih.gov/32232147/),
  [Science Robotics – running economy](https://www.science.org/doi/10.1126/scirobotics.aay9108),
  [MIT Tech Review – sprint exo](https://www.technologyreview.com/2023/09/27/1080360/this-robotic-exoskeleton-can-help-runners-sprint-faster/))

---

## 4. El rol de Jarvis: dónde una capa de IA/control aporta de verdad

Jarvis (o cualquier capa de software/IA) **encaja** en la parte de arriba de la
cadena, y **no reemplaza** la ingeniería física de abajo.

**Donde sí aporta:**

- **Fusión de sensores y estimación de estado:** combinar IMU + fuerza + (EMG)
  para estimar fase de marcha, ángulos y "qué está por hacer" el usuario, con
  filtros/modelos robustos al ruido.
- **Estimación de intención y asistencia predictiva:** clasificar el modo (caminar
  plano, subir, bajar, parado, correr) y anticipar el torque dentro de la ventana
  del delay electromecánico. Acá el aprendizaje automático brilla (Stanford usó
  *human-in-the-loop optimization*; German Bionic usa ML para adaptarse al
  usuario).
- **Personalización / optimización online:** ajustar automáticamente timing y
  magnitud de la asistencia para **minimizar el costo metabólico de esa persona**
  —el hallazgo central de Stanford— en vez de una curva fija.
- **Coordinación de alto nivel y capa de seguridad supervisora:** monitorear
  estados anómalos, detectar caídas o fallos, disparar el modo seguro, registrar
  telemetría, dialogar con el usuario. Encaja perfecto con la naturaleza de Jarvis
  como agente de tool-calling con control de dispositivos.

**Donde NO reemplaza a la ingeniería:**

- El **lazo de control de bajo nivel del motor** (FOC, corriente, torque) tiene
  que correr en firmware determinístico de tiempo real —microsegundos/
  milisegundos—, **no** en un LLM ni en un lazo de red. Un modelo de lenguaje no
  cierra un lazo de par a 1 kHz.
- La **seguridad dura** (límites de torque, watchdog, E-stop, backdrivability
  mecánica) vive en hardware/firmware, no en IA. La IA *supervisa*; el hardware
  *garantiza*.
- La **física** (actuador, batería, estructura, alineación) no se resuelve con
  software: si el motor no tiene torque o la batería no tiene energía, ninguna IA
  lo arregla.

**Arquitectura sana:** firmware de tiempo real por articulación (control de motor
+ seguridad) ↔ un controlador de marcha en tiempo real (fase, torque objetivo) ↔
**Jarvis** como capa de supervisión/intención/personalización/telemetría por
encima. Jarvis es el copiloto estratégico, no el que mueve el músculo.

---

## 5. Seguridad: por qué se empieza por prototipos que no cargan el cuerpo

Un motor con reductor acoplado a tu articulación puede aplicar más par del que tu
cuerpo tolera, en la dirección equivocada, en milisegundos. Los riesgos reales:
hiperextensión/torsión articular, pinzamiento de tejidos, caídas por asistencia
mal-timed, quemaduras/lesión por puntos de presión, y fallas eléctricas (batería
LiPo).

Principios de **fail-safe** que la industria ya da por sentados —y que conviene
adoptar desde el prototipo #1:

- **Backdrivability por diseño:** si el sistema se apaga o cuelga, el usuario debe
  poder mover la articulación libremente. Reductores bajos/QDD o embragues ayudan.
- **Límites de torque y de rango** en hardware/firmware, independientes del
  software de alto nivel. Topes mecánicos que impidan superar el rango anatómico.
- **Watchdog + E-stop físico** al alcance del usuario, más apagado automático ante
  estados anómalos.
- **Empezar en banco, sin humano:** probar el actuador y el control contra una
  carga inerte o un dummy antes de acoplarlo a un cuerpo. Después, probar sobre el
  cuerpo **sin que el exo soporte el peso del usuario** (como el EksoNR, que es
  autosoportado y no descarga su masa sobre el paciente).
- **Progresión de par:** empezar con asistencia mínima (pocos N·m) y subir sólo
  cuando el control es estable y predecible.
- **BMS y protección de batería** serios: las LiPo mal tratadas son un riesgo de
  incendio.

Regla que ordena todo: **el software puede fallar; el hardware no te debe poder
lastimar cuando falla.**

---

## 6. Veredicto honesto y motivador

**Lo honesto:** nadie construye un traje de Iron Man en el garage, y el aumento de
fuerza full-body está fuera de alcance sin una organización. Los dos muros —
**energía** (densidad de batería) y **control en tiempo real** (intención +
latencia + seguridad)— no se rompen con entusiasmo, se rodean con alcance
acotado. Y "correr al doble de velocidad" no es lo que la física permite hoy;
"correr/caminar gastando 15–25% menos energía" **sí**.

**Lo motivador —y también honesto:** una sola persona con tiempo, la electrónica
de robótica open-source de 2026 y método **sí** puede construir cosas reales y
útiles, en este orden:

1. **Exosuit pasivo de espalda** (semanas–meses): mecánico/textil, sin riesgo de
   software, resultado medible. Aprendés acople humano-máquina.
2. **Asistencia motorizada de un tobillo o una cadera** (muchos meses): tu primer
   sistema activo real, con el objetivo *demostrable* de bajar el costo
   metabólico de caminar/subir escaleras. Aquí Jarvis empieza a aportar de verdad
   (fusión de sensores, fase de marcha, asistencia predictiva, seguridad
   supervisora).
3. **Recién entonces**, quizás, coordinar dos articulaciones. El salto a
   multi-articulación de fuerza/velocidad queda como horizonte, no como meta
   inmediata.

**Fuera de alcance sin organización:** full-body de amplificación de fuerza,
aumento de velocidad de sprint, hidráulica de alta potencia, certificación médica.

### Primer proyecto concreto y barato (punto de entrada recomendado)

**Un exosuit pasivo de asistencia lumbar, estilo HeroWear Apex, hecho por vos.**

- **Qué:** arnés de torso + muslos con **bandas elásticas** ruteadas para que, al
  inclinarte hacia adelante, parte de la carga de la espalda baja se transfiera a
  los muslos, y que se "desenganchen" al estar parado derecho para no molestar.
- **Por qué es el mejor primer paso:** costo bajo (textil + elásticos +
  impresiones 3D + una balanza/dinamómetro para medir), **cero** riesgo de motor
  descontrolado, y resultado **medible** (podés cuantificar reducción de esfuerzo
  con EMG barata de superficie o, más simple, con sensación y repeticiones). Te
  enseña el problema que más subestima todo el mundo —alineación, transmisión de
  fuerza, comodidad— antes de gastar un peso en actuadores.
- **Puente hacia Jarvis:** aunque el suit sea pasivo, podés instrumentarlo con una
  **IMU + un módulo EMG de superficie** que registre y clasifique tus movimientos
  de lifting. Eso te da el dataset y el pipeline de **estimación de intención**
  que después reutilizás en el peldaño 2 (asistencia motorizada). Jarvis arranca
  como capa de **telemetría y clasificación de marcha/gesto**, sin tocar todavía
  ningún motor — riesgo cero, aprendizaje máximo.

---

## Fuentes

- Sarcos Guardian XO — [IEEE Spectrum](https://spectrum.ieee.org/sarcos-guardian-xo-powered-exoskeleton) · [New Atlas](https://newatlas.com/sarcos-robotics-guardian-xo-exoskeleton/57847/) · [The Robot Report](https://www.therobotreport.com/rbr50-company/sarcos-robotics-commercializes-guardian-xo-full-body-exoskeleton-for-industrial-use/)
- German Bionic Apogee / Apogee Ultra — [Engadget](https://www.engadget.com/wearables/german-bionics-new-apogee-ultra-exoskeleton-can-lift-up-to-80-pounds-and-help-with-walking-140031689.html) · [The Robot Report](https://www.therobotreport.com/german-bionic-debuts-apogee-powered-exoskeleton/) · [automation.com](https://www.automation.com/article/german-bionic-apogee-ultra-powerful-exoskeleton)
- Lockheed Martin ONYX / Dermoskeleton — [Breaking Defense](https://breakingdefense.com/2019/10/knees-of-iron-lockheeds-onyx-exoskeleton/) · [Lockheed Martin](https://news.lockheedmartin.com/2018-11-29-Lockheed-Martin-Secures-U-S-Army-Exoskeleton-Development-Agreement)
- Ekso Bionics EksoNR — [Ekso Bionics](https://eksobionics.com/eksonr/) · [Rehacare](https://www.rehacare.com/en/media-news/emag/business/exoskeleton-rehabilitation)
- HeroWear Apex (pasivo de espalda) — [Exoskeleton Report](https://exoskeletonreport.com/2023/03/herowear-introduces-apex-2-the-next-generation-of-exosuits-for-reducing-back-injuries/) · [ScienceDirect (evaluación)](https://www.sciencedirect.com/science/article/abs/pii/S0021929021003912) · [autoevolution](https://www.autoevolution.com/news/herowear-apex-exosuit-is-the-next-generation-of-free-movement-exoskeletons-164072.html)
- Stanford, Slade et al., *Nature* 2022 (optimización real-world del exo de tobillo) — [Nature](https://www.nature.com/articles/s41586-022-05191-1) · [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC9556303/)
- Harvard Biodesign / Wyss (exosuits blandos, costo metabólico) — [Harvard Biodesign](https://biodesign.seas.harvard.edu/soft-exosuits) · [Science Robotics (running)](https://www.science.org/doi/10.1126/scirobotics.aan6708)
- Actuadores SEA / QDD / BLDC — [Cambridge (SEA knee exo)](https://www.cambridge.org/core/journals/wearable-technologies/article/serieselastic-actuator-with-two-degreeoffreedom-pid-control-improves-torque-control-in-a-powered-knee-exoskeleton/FBEBF3966808F9AC51138792D3B6BF10) · [Actuator deep dive](https://www.wasilzafar.com/pages/series/sensors-actuators/sensors-actuators-actuator-robotic-joint.html) · [Frontiers – OpenSEA](https://www.frontiersin.org/journals/robotics-and-ai/articles/10.3389/frobt.2025.1528266/full)
- Energía / densidad de batería — [Reporte energía exos (PatSnap)](https://eureka.patsnap.com/report-harness-renewable-energy-sources-for-exoskeleton-power)
- Control EMG / intención / latencia — [Review onset EMG (JNER)](https://link.springer.com/article/10.1186/s12984-023-01268-8) · [Myoelectric control review (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9655258/)
- Velocidad de carrera / límites — [ScienceAlert (catapulta 50%)](https://www.sciencealert.com/using-a-catapult-like-exoskeleton-could-get-us-running-50-percent-faster) · [PubMed ("run 50% faster")](https://pubmed.ncbi.nlm.nih.gov/32232147/) · [Science Robotics (running economy)](https://www.science.org/doi/10.1126/scirobotics.aay9108) · [MIT Tech Review (sprint exo)](https://www.technologyreview.com/2023/09/27/1080360/this-robotic-exoskeleton-can-help-runners-sprint-faster/)
- Milicia China (contexto de despliegue real) — [Defense One](https://www.defenseone.com/technology/2025/08/iron-man-himalayas-chinas-pla-embraces-exoskeletons/407797/) · [Global Times](https://www.globaltimes.cn/content/1209633.shtml)

---

*Documento generado el 2026-08-18. Basado en sistemas y literatura reales; los
números citados provienen de las fuentes enlazadas. No incluye contenido de
armamento — marco estrictamente asistivo/de aumento (carga, movilidad, economía
de esfuerzo).*
