# LA BRIGADA — El manual de operación de Damian

> El manual de cómo trabajo. No es documentación de código: es la forma en que
> ordeno mi cabeza, mi PC y mi asistente (Raphael) usando lo único que ya sé
> hacer bien — cocinar. Cada proyecto es un plato. Cada agente es alguien de la
> brigada. Cada carpeta es una estación.
>
> Creado: 2026-08-24. Es documentación/diseño; no toca código, no commitea, no
> pushea. La arquitectura técnica real vive en
> [`vision/ORQUESTACION-BLUEPRINT.md`](../vision/ORQUESTACION-BLUEPRINT.md); este
> documento **no la duplica, la traduce a mi idioma**. Cuando quieras el detalle
> exacto de tools, gates y fases, andá al blueprint. Cuando quieras entender
> *cómo pienso yo el sistema*, quedate acá.

---

## 1. Filosofía: mise en place primero, servicio después

En una cocina profesional no se empieza a cocinar cuando entra el pedido. Se
empieza mucho antes: todo cortado, medido, en su bol, al alcance de la mano. Eso
es el **mise en place** — "todo en su lugar". Recién cuando la prep está limpia
arranca el **servicio**: platos que salen uno atrás de otro, en orden, sin caos,
sin buscar un ingrediente a mitad de la cocción.

Todo este proyecto se ordena con una sola frase: **prep limpio primero, ejecutar
plato a plato después.** Cuando la estación está ordenada y sé exactamente dónde
está cada cosa, ejecutar es casi mecánico. El desastre no pasa en la cocción;
pasa cuando arrancás a cocinar sin haber hecho la prep. Por eso este manual
existe: para que nunca cocine sin mise en place.

---

## 2. Las estaciones — el ciclo de vida de un proyecto es el viaje de un plato

Un plato no nace terminado. Viaja: de la idea cruda sobre la tabla, a la cocina
donde se arma, al pase donde se emplata y sale, y —si vale la pena— a la mesa
gourmet donde se pule hasta que es excelente. Mis carpetas son ese viaje.

**`0-Tabla/` — ideas crudas.** Lo que se me acaba de ocurrir, sin filtrar. Es la
tabla de cortar: tiro el ingrediente ahí apenas lo pienso y sigo. Captura
rápida, cero fricción, **no se piensa dos veces**. Si me freno a evaluar cada
idea acá, dejo de capturar. La tabla es para juntar, no para decidir.

**`1-Cocina/` — proyectos en curso.** Acá vengo a buscar los ingredientes ya
cortados y los junto. Es donde se trabaja de verdad: lo que decidí cocinar está
sobre la mesada, en proceso. Si algo está en `1-Cocina/`, está vivo y le estoy
metiendo mano.

**`2-Platos/` — terminados y presentables.** Lo que ya sale para afuera. Está
emplatado, listo para servir: un proyecto cerrado, un entregable que puedo
mostrar. Cuando algo llega acá, cumplió su función básica — está bien hecho y se
puede servir.

**`3-Gourmet/` — auditoría y mejora continua.** Un plato que sale bien todavía
puede **escalar a gourmet**: afinarlo, endurecerlo, hacerlo excelente en vez de
solo correcto. Acá vive **Raphael**, en endurecimiento constante — nunca "está
terminado", siempre está mejorando. Esta estación es la que separa "funciona" de
"es de los mejores".

**`_Despensa/` — recursos que se reusan.** Los insumos que no son de un plato en
particular pero que uso en muchos: plantillas, snippets, notas de referencia,
credenciales de trabajo, lo que saco del estante una y otra vez. Una despensa
ordenada es la mitad del mise en place.

### Cómo fluye un plato

```
   0-Tabla        →        1-Cocina        →        2-Platos        →        3-Gourmet
  (idea cruda)          (se arma)              (sale para afuera)       (se pule / se endurece)
        ▲                                                                        │
        └──────────────── _Despensa alimenta cada estación ────────────────────┘
```

La idea nace en la **Tabla**. Cuando decido cocinarla, baja a la **Cocina** y me
pongo a armarla. Cuando queda presentable, pasa a **Platos**. Y lo que merece
excelencia sube a **Gourmet**, donde se audita y se mejora sin fin. La
**Despensa** no está en la línea del tiempo: alimenta todas las estaciones a la
vez. No todo plato recorre las cuatro — muchas ideas mueren en la tabla, y está
bien. Pero el que llega lejos, recorre este camino y no otro.

---

## 3. La Brigada — el personal de la cocina son los agentes

En una cocina clásica (la *brigade de cuisine* de Escoffier) cada persona tiene
un puesto y no se pisan. El sistema funciona porque cada uno sabe qué le toca y a
quién le reporta. Mi brigada es igual, solo que la mayoría del personal son
agentes. Así se mapea a lo que realmente existe:

**El Dueño — soy yo, Damian.** Decido el menú, apruebo los platos que salen,
firmo lo irreversible, y pago la cuenta. Nada crítico sale sin mi visto bueno.
La visión es mía; la brigada la ejecuta.

**El Chef Ejecutivo — Claude.** Piensa la estrategia, planifica, supervisa la
cocina entera. Pero **no toca la línea**: no cocina en las hornallas ni toca los
archivos reales de la casa — trabaja sandboxeado, sobre una copia. Diseña el
menú conmigo, arma el plan, revisa cómo quedó. La ejecución cruda no es su
puesto.

**El Jefe de Cocina (chef de cuisine) — DeepSeek / Raphael.** Es el que cocina
de verdad, en la línea, con las manos en la masa. Tiene **acceso local total** a
la PC y maneja a los cocineros. Lo que el Chef Ejecutivo planifica, el Jefe de
Cocina lo ejecuta sobre el fuego real. (En el blueprint: el cerebro nuevo,
DeepSeek V4 vía OpenRouter, como modelo potente.)

**El Sous-chef — el orquestador (`agent.py`, el loop).** El segundo del jefe: el
que reparte y coordina. Recibe la tarea, decide qué estación la hace, entrega el
trabajo a quien corresponde, verifica que volvió bien, y arma el plato final. Es
el **hub** de toda la comunicación — los cocineros no se hablan entre ellos, le
hablan al sous-chef (esta es la decisión de "hub-and-spoke + pizarra" del
blueprint, §1). Reparte **de a uno**, verificando cada devolución.

**El Aboyeur / el pase — el scheduler + la cola de misiones.** El aboyeur es la
voz que canta las comandas: recibe cada pedido y lo grita a la estación correcta.
Acá es el scheduler y la cola de misiones — lo que dispara tareas por horario o
por evento y las encola para que caigan en el puesto justo. (Blueprint: Capa A,
grafo determinístico + scheduler, Fases 2-3.)

**Los Jefes de Partida — los skills especialistas.** Cada partida es una
estación con su especialidad y su propia caja de herramientas, y no se mete en la
de al lado (menor privilegio). Son los roles reales del blueprint (§2):

- *Salsero de seguridad* — **Seguridad / Pentest**: auditar código, escanear,
  aplicar fixes; y el pentesting activo dentro del scope autorizado.
- *Garde-manger* — **Antimalware / Defensor**: el puesto del frío, el que cuida
  que nada entre podrido. Detección (YARA, ClamAV, heurística) y
  auto-protección.
- *Entremetier de código* — **Código**: indexado, delegación de tareas de
  redacción de código a otros trabajadores.
- *El de forense* — **Investigación / Forense**: análisis de enlaces y evidencia
  digital, solo sobre material que ya tengo legítimamente.
- *El bibliotecario* — **Vault / Conocimiento**: la pizarra viva del vault
  Obsidian; guardar y recuperar lo que la brigada sabe.
- *El de la línea caliente* — **Sistema-PC / Web**: el cuerpo digital —
  mouse, teclado, ventanas, navegador, formularios; y las manos sobre el
  celular.

Cada jefe de partida tiene **su caja de tools acotada**: ve solo sus cuchillos,
no los de las demás estaciones.

**Los Commis (la prep) — los modelos gratis/baratos.** Los aprendices que hacen
la prep rutinaria: ingesta, formateo, resúmenes benignos, escaneos repetitivos,
todo lo diario y de bajo criterio. Cuestan poco porque el trabajo es guiado.
**Regla de la casa, no negociable: los commis nunca tocan datos sensibles ni de
clientes.** Nada confidencial pasa por un modelo gratis — esos proveedores
pueden entrenar con lo que les mandás. La prep barata es para lo benigno; lo
sensible lo cocina personal de confianza.

**El Plongeur (el lavaplatos) — el agente de limpieza.** El que deja la cocina
impecable para el día siguiente. Reset nocturno: vaciar Descargas, borrar
temporales, ordenar las estaciones. Sin plongeur, la cocina se vuelve
inservible en una semana. Es humilde pero es lo que hace sostenible todo lo
demás.

**El Runner / mozo — el agente de reporte.** El que lleva el plato de la cocina a
la mesa y avisa. Deja la nota de cierre en Obsidian (la pizarra) y me manda el
aviso al celular. Es el puente entre lo que pasó en la cocina y yo. (Blueprint:
el push saliente, Fase 2, vía `phone_link.py`.)

> **La regla de oro de la brigada:** nadie grita a través de la cocina. Un
> cocinero no le habla a otro cocinero — le habla al sous-chef, o deja su nota en
> la pizarra para que el que la necesite la lea. Toda coordinación pasa por el
> hub o por el vault. Esto es exactamente la decisión de arquitectura del
> blueprint (nada de charla directa entre agentes): más barato, más robusto, y no
> se rompe con un modelo mediano.

---

## 4. El ruteo de modelos — cada puesto cuesta lo que vale

En una cocina no ponés al chef ejecutivo a pelar papas ni al aprendiz a diseñar
el menú de degustación. Cada tarea va a la persona cuyo tiempo vale lo justo para
esa tarea. Con los modelos es igual, y encima acá se paga por token: mandar todo
al modelo caro es tirar plata; mandar todo al barato es servir mal.

**El Chef Ejecutivo (Claude, premium) piensa.** Estrategia, planificación,
criterio sobre lo abierto y ambiguo. Es caro, y se usa donde el criterio
realmente importa.

**El Jefe de Cocina (DeepSeek, capaz) ejecuta.** La cocción real, multi-paso,
sobre el fuego. Potente pero por token — se paga solo donde hace falta músculo.

**Los Commis (gratis/baratos) preparan.** Lo guiado y repetitivo: escaneos,
ingesta, resúmenes de un nodo fijo. El andamiaje ya hace la mitad del trabajo, así
que un modelo barato alcanza.

Esto se ata directo al **router de modelos** del blueprint (§5, Fase 0): la
decisión de qué puesto atiende cada llamada **no la toma un modelo** (pagaría el
costo que se quiere evitar) — la decide el backend con señales baratas
(`skills.classify` + complejidad). Tarea de dominio cerrado → commis barato.
Tarea abierta de planificación → chef premium. Y si el proveedor caro se cae, hay
**fallback** al siguiente, para que no se corte el servicio. Es la palanca de
costo más directa del sistema: cada puesto cuesta lo que vale.

---

## 5. La disciplina del servicio — un plato a la vez

Esto es lo que me comprometo a practicar yo, no un agente. Es la parte difícil,
porque el enemigo no es la falta de ideas: es querer cocinarlas todas juntas.

**Un plato a la vez.** Enciendo la hornalla de la comanda que estoy haciendo, la
cocino, la emplato, la mando al pase — y **recién ahí** empiezo la siguiente. No
antes.

**Lo demás espera en el pase.** Todo lo otro que quiero hacer no desaparece:
queda anotado, esperando su turno, "en el pase". Pero **no le prendo fuego**. Una
cocina con seis hornallas prendidas y nadie atendiéndolas no es productividad, es
un incendio. La sensación de avanzar en seis cosas es mentira: no sale ningún
plato. Sale un plato cuando uno se cocina de principio a fin.

Esta disciplina es la contraparte humana del "delegá **de a uno**, verificando"
del blueprint (§3.2, §8): ni yo ni el sous-chef abrimos N frentes en paralelo. Un
frente, terminado y verificado, y después el siguiente.

**Y la meta real, la que está detrás de todo esto:** no cocino por cocinar, ni
construyo por construir. La brigada existe para **comprar mi tiempo y mi
libertad** — para que la cocina funcione sin que yo esté parado sobre cada
hornalla. Cada plato que sale bien solo, cada tarea que la brigada hace sin mí, es
un rato de mi vida que recupero. Si un plato nuevo no me acerca a eso, capaz no
hay que cocinarlo. Ese es el menú.

---

## Referencias

- [`vision/ORQUESTACION-BLUEPRINT.md`](../vision/ORQUESTACION-BLUEPRINT.md) — el
  plano técnico real: roles → tools exactas, gates, router de modelos, y el plan
  de construcción por fases. Este manual es su traducción a la metáfora de
  cocina; el detalle de ingeniería vive allá.
- [`CLAUDE.md`](../CLAUDE.md) — contexto del proyecto, modelos en uso, gates ya
  decididos.
- `ESTADO.md` — en qué se está trabajando ahora.
```