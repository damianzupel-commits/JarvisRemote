# ORQUESTACION-REMOTA-DESIGN.md — Orquestación remota de Jarvis desde el celular

> **Documento de diseño (no ejecutable).** Describe cómo Damian puede controlar
> a Jarvis desde el celular **estando fuera de casa** para que actúe como una
> extensión suya sobre el cyber range: abrir/manejar las VMs del lab, lanzar
> tareas de pentesting/detección dentro de `labnet`, y reportar de vuelta — todo
> **sin debilitar ni un solo gate existente**.
>
> Creado: 2026-08-17. Alcance: **solo diseño**. No instala, no ejecuta, no toca
> config. Pensado para implementarse después por fases (§10).
>
> Alinea con: `lab/CYBER-RANGE-DESIGN.md` (topología del range, blancos,
> snapshots), `lab/DETECCION-ESTRES-NOCTURNO.md` (bucle de detección/emulación),
> `lab/RETOMAR-LAB.md` (estado actual del armado), `CLAUDE.md` (arquitectura,
> modelos, gates) y el código real del backend (`backend/app/`).

---

## 1. Objetivo y encuadre

### 1.1 Qué queremos

Que Damian, desde el celular y sin estar en casa, le pueda decir a Jarvis cosas
como *"levantá el range y corré un recon sobre Metasploitable"* o *"arrancá la
prueba de estrés de detección de esta noche y avisame cómo viene"*, y que Jarvis
lo **ejecute de verdad** en la PC de casa —abrir/manejar las VMs del cyber range,
lanzar las herramientas ofensivas/defensivas dentro de `labnet`, y volcar los
resultados a Obsidian y de vuelta al celular— comportándose como **una extensión
de Damian**: la misma persona, la misma intención, con más manos.

Esto **no es una capacidad nueva de Jarvis**: Jarvis ya sabe manejar VMs vía
shell, ya corre las tools de pentest, ya escribe al vault. Lo nuevo es **el canal
remoto seguro y la capa de orquestación** (cola de misiones + confirmaciones
remotas) que dejan hacer todo eso desde afuera de casa, de forma ordenada.

### 1.2 El límite, dicho de una vez

**"Extensión de Damian" no significa "sin gates".** Que la orden venga del celular
de Damian, autenticada, desde afuera de casa, **no cambia nada** respecto de las
reglas que ya rigen a Jarvis. En particular:

- El guardrail de `authorized_targets.yaml` sigue siendo el control técnico de
  scope. Ningún camino remoto puede ampliarlo: solo Damian edita ese archivo a
  mano, en la PC, fuera del chat (ver `app/network/guardrail.py`, y §6).
- Las categorías peligrosas —borrar datos, mover dinero, cambiar config del
  sistema, tocar un blanco fuera de scope— **siguen requiriendo confirmación
  explícita de Damian**, aunque la sesión sea remota (ver §7.4 y §9).
- Los patrones ya decididos se respetan tal cual: `dry-run → confirm=true` para
  lo irreversible, `preview_token` de un solo uso para submits de formularios,
  `proposal_id` para auto-reparación, blocklist + auditoría para shell.

El canal remoto **agrega una puerta de entrada** (autenticada, cifrada, privada);
no abre ninguna de las puertas internas que ya están cerradas.

---

## 2. Arquitectura general

```
   ┌─────────────────┐
   │  Celular Damian │   (fuera de casa: datos móviles / WiFi ajeno)
   │  app JarvisRemote│
   └────────┬────────┘
            │  1) Tailscale: red privada malla, cifrada (WireGuard),
            │     tráfico solo entre dispositivos del tailnet de Damian.
            ▼
   ┌───────────────────────────────────────────────────────────────┐
   │                    PC de casa (Windows)                        │
   │                                                                │
   │   Tailscale (interfaz 100.x.y.z)                               │
   │            │  2) endpoint autenticado (Bearer/JWT),           │
   │            │     escuchando SOLO en la interfaz Tailscale     │
   │            ▼                                                    │
   │   ┌────────────────────┐                                       │
   │   │  Backend Jarvis     │  FastAPI (app/main.py)               │
   │   │  /api/chat, /ws/... │  + cola de misiones (nuevo, §7)      │
   │   └─────────┬──────────┘                                       │
   │             │  3) agente (app/agent.py): loop LLM → tool → LLM │
   │             ▼                                                    │
   │   ┌────────────────────────────────────────────────────┐      │
   │   │  Tools del agente (app/tools/)                      │      │
   │   │   • vm_control  → VBoxManage  (nuevo, §5)           │      │
   │   │   • ssh_guest   → SSH a Kali  (nuevo, §6)           │      │
   │   │   • nmap/sqlmap/zap/... (existentes, gated)         │      │
   │   │   • obsidian_*  → vault de notas (existente)         │      │
   │   └─────────┬──────────────────────────┬────────────────┘      │
   │             │                          │                       │
   │             ▼                          ▼                       │
   │   ┌──────────────────┐      ┌──────────────────────┐          │
   │   │ VirtualBox        │      │  Vault Obsidian       │          │
   │   │  VM Kali (atacante)│─────▶│  (reporte/aprendizajes)│         │
   │   │  VM Metasploitable │      └──────────┬───────────┘          │
   │   │  … blancos labnet  │                 │                      │
   │   │  10.13.37.0/24     │                 │ 4) reporte           │
   │   └──────────────────┘                 ▼                      │
   │        (red interna, sin salida)   de vuelta al celular         │
   └───────────────────────────────────────────────────────────────┘
```

Flujo de una orden: **celular → Tailscale (cifrado, privado) → endpoint
autenticado de Jarvis (solo interfaz Tailscale) → agente Jarvis → `VBoxManage` /
SSH a Kali / módulos de pentest existentes (todo dentro de `labnet`) → reporte a
Obsidian y de vuelta al celular.**

Nada de esto expone puertos a internet ni abre nada en el router (§3.4). El
tráfico ofensivo sigue naciendo dentro de `labnet` (Jarvis → Kali → blancos, la
conexión recomendada del diseño del range, §6.2).

---

## 3. Canal remoto seguro con Tailscale

### 3.1 Lo que ya existe

Tailscale ya está instalado y en uso en este proyecto: el backend detecta su
propia IP de Tailscale y la ofrece como **candidato de conexión de respaldo** al
celular (ver `app/network_info.py`: `TAILSCALE_RANGE = 100.64.0.0/10`, tipo
`"tailscale"` con prioridad más baja que hotspot/LAN directa). El guardrail de
pentest ya reusa ese mismo rango como parte del scope permitido por default (ver
`app/network/guardrail.py`). Es decir: la red privada ya está armada; lo que falta
es **atar el endpoint remoto a ella y solo a ella**.

Tailscale arma una **red malla privada cifrada con WireGuard** entre los
dispositivos de la cuenta de Damian (su "tailnet"). Por diseño, **todo el tráfico
entre dispositivos del tailnet va cifrado y deny-by-default**: dos nodos solo se
hablan si una regla lo permite ([Tailscale — Access control](https://tailscale.com/kb/1393/access-control)).
Eso es exactamente el modelo que queremos: el celular y la PC son dos nodos del
mismo tailnet; nadie más entra.

### 3.2 Atar el backend SOLO a la interfaz Tailscale

Hoy el backend escucha en `0.0.0.0` (ver `app/config.py`: `host = HOST` default
`"0.0.0.0"`, y el comentario en `app/network_info.py`: *"El backend ya escucha en
0.0.0.0 … acepta conexiones por cualquier interfaz simultáneamente"*). Para el
canal remoto eso es demasiado abierto: `0.0.0.0` incluye la LAN doméstica y
cualquier red a la que la PC esté conectada.

**Decisión de diseño:** el endpoint remoto debe escuchar **únicamente en la IP de
Tailscale de la PC** (la `100.x.y.z` del nodo), no en `0.0.0.0`. Dos formas de
lograrlo, en orden de preferencia:

1. **`tailscale serve` (preferido).** Se deja el backend escuchando en
   `127.0.0.1` (localhost puro, inalcanzable desde cualquier red) y se usa
   `tailscale serve` para exponerlo **solo dentro del tailnet**. Es el patrón que
   la propia documentación recomienda: *"only have the service listen on
   localhost"* y dejar que Serve lo publique en la tailnet, heredando
   automáticamente las reglas de acceso del tailnet
   ([Tailscale Serve examples](https://tailscale.com/docs/reference/examples/serve)).
   Ventaja extra: `tailscale serve` puede terminar TLS con un certificado del
   tailnet, resolviendo de fondo el "hoy viaja en texto plano" que hoy tapa el
   flag `TLS_ENABLED=false` (ver `app/config.py`) — sin tener que hacer que
   Android confíe en un cert self-signed (el corte que `certs/README.md` pide
   coordinar). WireGuard ya cifra el transporte de punta a punta aunque el
   backend hable HTTP; Serve suma HTTPS "de verdad" arriba.
2. **Bind explícito a la IP de Tailscale.** Alternativa sin Serve: setear `HOST`
   a la `100.x.y.z` concreta del nodo (o resolverla al arranque desde
   `network_info`). Funciona, pero es más frágil (la IP de Tailscale es estable
   pero conviene resolverla, no hardcodearla) y no aporta la terminación TLS que
   sí da Serve. Queda como plan B.

En ambos casos, la regla es la misma: **el puerto de Jarvis nunca queda accesible
desde la LAN doméstica, WSL2, ni internet** — solo desde el tailnet.

### 3.3 ACLs / grants del tailnet: mínimo privilegio

Tailscale es deny-by-default, pero conviene **estrechar todavía más** con una
regla explícita en el policy file, siguiendo mínimo privilegio: que **solo el
celular de Damian** pueda alcanzar **solo el puerto de Jarvis** en la PC. La forma
moderna son los *grants* (Tailscale marca los ACLs clásicos como legacy y
recomienda migrar a grants para configuraciones nuevas —
[Manage permissions using ACLs](https://tailscale.com/docs/features/access-control/acls)).

Esquema conceptual (huJSON, a completar por Damian con sus tags reales):

```jsonc
// Idea, no config final. Etiquetar la PC como tag:jarvis-host y el
// celular como tag:damian-phone, y permitir SOLO ese par y ese puerto.
{
  "grants": [
    {
      "src": ["tag:damian-phone"],
      "dst": ["tag:jarvis-host"],
      "ip":  ["tcp:8000"]        // el puerto real del backend / de tailscale serve
    }
  ]
}
```

Con eso, aunque un tercer dispositivo entrara al tailnet (otra máquina de Damian,
por ejemplo), **no** podría hablarle a Jarvis salvo que se lo agregue
explícitamente. Es la misma filosofía de `authorized_targets.yaml`: lista blanca
chica, editada a mano.

### 3.4 Por qué NO se abren puertos en el router

Tentación clásica: "abrí el 8000 en el router y listo". **No.** Abrir un puerto
(port forwarding / DMZ) publica el servicio **en la internet pública**, donde:

- Cualquiera en el mundo puede encontrarlo (Shodan, escaneos masivos) e intentar
  fuerza bruta sobre el token, explotar un bug de FastAPI/uvicorn, o simplemente
  DoS-earlo.
- La superficie de ataque deja de ser "un dispositivo de confianza en una red
  privada" y pasa a ser "todo internet".
- Contradice frontalmente el criterio que ya vive en el código:
  `network_info._classify` devuelve `None` para cualquier IP pública con el
  comentario *"IP pública: nunca se ofrece como candidato (nada expuesto a
  internet)"*.

Tailscale da el mismo resultado funcional (llegar a la PC desde afuera) **sin**
exponer nada: el "pinchazo" a través del NAT lo hace Tailscale con conexiones
cifradas y autenticadas entre pares, no un agujero abierto en el router. Regla
del documento: **el router no se toca; todo remoto entra por Tailscale.**

---

## 4. Autenticación del endpoint remoto

### 4.1 De dónde partimos

El backend ya autentica con un **Bearer token único** (`app/auth.py`:
`verify_api_key`, compara contra `settings.api_key`; el mismo token protege
`/api/chat` y el WebSocket `/ws/phone` vía `_check_bearer` en `app/main.py`). El
token vive en `API_KEY` dentro de `backend/.env` (si falta, se genera uno al
arranque y se imprime). Funciona, pero para el canal remoto tiene tres
debilidades: (a) es **un solo secreto compartido** para todo y todos; (b) no
expira ni rota; (c) vive en `.env` en **texto plano** (el propio proyecto ya
señaló ese antipatrón al diseñar el credential store de formularios y el de
malware — ver `app/forms/credential_store.py`).

### 4.2 Esquema propuesto: token por dispositivo, guardado con DPAPI

Dos capas de autenticación, de afuera hacia adentro:

1. **Capa de red (Tailscale):** ya autentica *el dispositivo* — solo nodos del
   tailnet de Damian llegan al puerto (§3). Es la primera línea y la más fuerte.
2. **Capa de aplicación (token):** además, cada request trae un **token por
   dispositivo**. No un secreto global compartido, sino **una credencial emitida
   para el celular de Damian**, revocable y rotable sin tocar el resto.

**Dónde se guarda (reusar el patrón que ya existe):** los tokens emitidos se
persisten cifrados con **DPAPI**, el mismo mecanismo que ya usan
`app/forms/credential_store.py` (credenciales de formularios) y
`app/investigation/keys.py` (clave Ed25519 del audit log). DPAPI ata el cifrado a
la cuenta de Windows de Damian en esta máquina: nadie puede descifrar el archivo
copiándolo a otra PC o leyéndolo con otra cuenta. **Nunca en `.env` en claro,
nunca en la URL** (un token en la query string queda en logs, historiales y
proxies) — siempre en el header `Authorization`, como ya hace `verify_api_key`.

**Forma del token — dos opciones equivalentes:**

- **Token opaco por dispositivo (más simple, recomendado para arrancar).** Un
  string aleatorio fuerte (`secrets.token_urlsafe`, igual que el fallback actual
  de `API_KEY`), uno por dispositivo, guardado en el store DPAPI junto con un
  `device_id`, fecha de alta y fecha de expiración. Validar = buscar el token en
  el store y chequear que no esté vencido ni revocado. Suficiente para un tailnet
  de un solo usuario.
- **JWT firmado con refresh rotation (más robusto, para más adelante).** Access
  token corto (5–15 min) + refresh token rotado en cada uso y revocable del lado
  server, que es la práctica recomendada 2026 para tokens de API
  ([JWT refresh token rotation](https://codecondo.com/jwt-refresh-token-rotation/),
  [LogRocket — JWT best practices](https://blog.logrocket.com/jwt-authentication-best-practices/)).
  Da revocación fina y ventana de robo mínima, a costa de más maquinaria. Para
  un único usuario detrás de Tailscale es probablemente sobre-ingeniería en fase
  1; se deja anotado como evolución natural si algún día hay más dispositivos.

### 4.3 Rotación y revocación

- **Rotación:** el token por dispositivo tiene fecha de expiración; al vencer, se
  emite uno nuevo desde la PC (o vía un endpoint de refresh autenticado con el
  token viejo aún válido). Rotar secretos periódicamente es práctica estándar
  ([API Authentication Best Practices 2026](https://skycloak.io/blog/api-authentication-best-practices/)).
- **Revocación:** si se pierde el celular, Damian borra la entrada del store DPAPI
  (o marca `revoked`) desde la PC y el dispositivo queda afuera **sin** tener que
  cambiar el secreto de ningún otro dispositivo. Con el `API_KEY` único de hoy,
  perder el celular obliga a rotar el secreto de todo.
- **Compatibilidad:** el `API_KEY` actual puede seguir funcionando para el uso en
  LAN/localhost durante la transición; el token por dispositivo es un requisito
  adicional para el camino remoto, no un reemplazo abrupto.

---

## 5. Tool de control de VMs (`vm_control`) — spec, no código

Un wrapper fino sobre **`VBoxManage`** (el CLI de VirtualBox — recordar que el lab
fue con VirtualBox, el "plan B" del diseño del range: sin auto-snapshots, se
scriptean con `VBoxManage snapshot`, ver `lab/RETOMAR-LAB.md §1`). Sigue el mismo
molde que las tools existentes de shell: se apoya en `app/shell_exec.py` (mismo
núcleo de subprocess + timeout duro + kill de árbol que ya usa `pc_run_command`),
se registra con `register_tool`, y **audita cada invocación** en el audit log
(`target="vm"`), en línea con `pc_command.py`.

### 5.1 Operaciones (todas de solo-control de VMs, ninguna arbitraria)

| Operación            | `VBoxManage` subyacente (referencia)                         | Notas |
|----------------------|--------------------------------------------------------------|-------|
| `list`               | `VBoxManage list vms` / `list runningvms`                    | Inventario. |
| `status`             | `VBoxManage showvminfo <vm> --machinereadable`               | Estado (running/poweroff/saved), IP si hay guest additions. |
| `start`              | `VBoxManage startvm <vm> --type headless`                    | **Headless** (sin ventana): es una PC remota, nadie mira la GUI. |
| `stop` (grácil)      | `VBoxManage controlvm <vm> acpipowerbutton`                  | Apagado ordenado. |
| `savestate`          | `VBoxManage controlvm <vm> savestate`                        | Congela y libera CPU/RAM sin perder estado. |
| `snapshot take`      | `VBoxManage snapshot <vm> take <nombre>`                     | Convención de nombres del diseño (§7.1 del range: `<blanco>-BASE-limpio`, PRE/POST). |
| `snapshot restore`   | `VBoxManage snapshot <vm> restore <nombre>`                  | Volver a limpio tras un ataque. |
| `snapshot list`      | `VBoxManage snapshot <vm> list`                              | Ver árbol de snapshots. |

Deliberadamente **no** se expone `VBoxManage modifyvm`, `unregistervm`, borrado de
discos, ni nada que cambie la topología o destruya VMs: esta tool orquesta el
ciclo encender/apagar/snapshot del lab, no rediseña el lab.

### 5.2 Validación de nombres permitidos (allow-list de VMs del lab)

Igual que el pentest valida el target contra `authorized_targets.yaml`, **esta
tool valida el nombre de la VM contra una allow-list de las VMs del lab** antes de
ejecutar nada. Solo `Kali`, `Metasploitable2`, y los blancos del range definidos
por Damian pueden ser tocados. Cualquier otro nombre (una VM personal, una de
trabajo) se **rechaza en el código**, no por prompt.

- La allow-list conceptualmente es análoga a `authorized_targets.yaml`: **una
  fuente única, editada por Damian, que ni la tool ni el LLM pueden escribir**.
  Podría ser un `lab/authorized_vms.yaml` con el mismo criterio de "solo Damian lo
  toca a mano", o reutilizar/extender el propio `authorized_targets.yaml` para no
  multiplicar listas (la decisión del 2026-08-13 fue justamente evitar tener seis
  listas que se desincronizan). Se recomienda archivo separado `authorized_vms`
  para no mezclar semánticas (una es "IPs que puedo atacar", la otra "VMs que
  puedo encender").
- **Destructivo con confirmación:** `snapshot restore` descarta el estado actual
  de la VM (irreversible para lo que hubiera sin snapshot) y `stop` sobre algo en
  medio de un trabajo puede perder resultados. Estas caen bajo la regla de §7.4 /
  §9: si Jarvis las decide de forma autónoma dentro de una misión, requieren
  confirmación de Damian; si son parte explícita de la orden, se ejecutan y se
  auditan.

### 5.3 Logging al audit log firmado

Cada operación (VM, acción, snapshot, resultado, timestamp) se registra en el
audit log. El proyecto ya tiene un audit log **firmado con Ed25519** en el módulo
de investigación (`app/investigation/keys.py`, clave protegida con DPAPI), y el
módulo de malware lo reusa para su propio log append-only. `vm_control` debería
escribir con el mismo mecanismo firmado, de modo que la traza de "qué se encendió
/ apagó / restauró y cuándo" sea igual de verificable e inalterable que un caso de
investigación o un hallazgo de malware. Esto importa el doble en operación remota:
es la evidencia de qué hizo Jarvis mientras Damian no estaba mirando la pantalla.

---

## 6. Ejecución dentro del guest: SSH a Kali (`ssh_guest`)

### 6.1 Por qué SSH y no "adentro del host"

El diseño del range ya fija la conexión recomendada: **Jarvis → Kali → blancos**
(`lab/CYBER-RANGE-DESIGN.md §6.1`, repetido en `RETOMAR-LAB.md §4`). Jarvis
*orquesta* desde el host Windows, pero las herramientas ofensivas pesadas
(recon, escaneo, emulación) **nacen dentro de `labnet`**, lanzadas desde Kali, que
es quien tiene la placa en el segmento aislado. Eso mantiene el tráfico ofensivo
donde tiene que estar (adentro del lab) y evita que salga por el host.

Para lanzar esas herramientas dentro de Kali de forma programática, la vía natural
es **SSH**: Jarvis abre una sesión SSH a Kali y corre ahí `nmap`, `sqlmap`, los
agentes de Caldera, etc.

### 6.2 Cómo se conecta Kali (dos interfaces)

Hoy Kali tiene **Adaptador 1 = labnet** (la placa de ataque, aislada) y
**Adaptador 2 = NAT** (solo para `apt update`, apagable durante ataques) — ver
`RETOMAR-LAB.md §1`. Para SSH-desde-el-host hace falta un camino de **gestión** que
no rompa el aislamiento de labnet:

- **Opción recomendada:** una tercera placa **host-only** dedicada a gestión (o
  usar la NAT existente con port-forward de solo el 22 al host), separada de
  labnet. Jarvis-en-el-host SSH-ea a Kali por esa interfaz de gestión; Kali ataca
  por su interfaz de labnet. Los blancos **nunca** ven la interfaz de gestión, así
  que el aislamiento del range (§3 del diseño: labnet sin ruta al host/LAN/WSL2)
  se mantiene. La interfaz de gestión es solo Jarvis↔Kali.
- **Credenciales SSH:** clave SSH dedicada del host a Kali, con la privada
  guardada bajo el mismo criterio DPAPI que el resto de secretos del proyecto (no
  en claro en el repo — el `.gitignore` ya bloquea `id_rsa*`, `*.pem`, `*.key`).
  Usuario `kali` (ver `RETOMAR-LAB.md §2b`).

### 6.3 Spec de la tool `ssh_guest`

Wrapper fino, mismo molde que `vm_control`: valida el host destino contra la
allow-list del lab (solo Kali / hosts de gestión del range), corre el comando por
SSH con timeout duro (reusar el patrón de `shell_exec`), trunca la salida (igual
que `MAX_OUTPUT_CHARS`), y **audita** cada ejecución. **No** es un shell libre a
cualquier host: es "ejecutar en Kali del lab", acotado.

### 6.4 Los blancos siguen restringidos por `authorized_targets.yaml`

Punto que no se negocia: **aunque el comando se lance desde Kali por SSH, el blanco
sigue estando restringido**. Hay dos capas que lo garantizan:

1. **Cuando el que llama la herramienta de ataque es una tool de Jarvis**
   (`nmap_scan`, `sqlmap_scan`, `zap_scan`, `packet_capture_*`), el guardrail de
   `app/network/guardrail.py` valida el target contra `authorized_targets.yaml`
   **antes** de ejecutar, y "el usuario dijo que sí en el chat" nunca es un camino
   de autorización — solo el archivo, editado a mano, cuenta.
2. **Todo corre dentro de `labnet` (`10.13.37.0/24`)**, que es un rango privado sin
   salida a internet ni ruta a la LAN real. Aunque un comando SSH crudo intentara
   apuntar afuera, la red del lab no tiene por dónde salir.

La conexión con el módulo de pentest y con el diseño de estrés de detección es
directa: `ssh_guest` es el brazo ejecutor dentro de labnet que lanza las técnicas
de Atomic Red Team / Caldera de `DETECCION-ESTRES-NOCTURNO.md` y las tools
ofensivas de recon/escaneo — pero **la decisión de qué es un blanco legítimo la
sigue tomando el gate, no el prompt ni el celular**.

---

## 7. Cola de "misiones"

El corazón de "Jarvis como extensión de Damian estando afuera": Damian manda una
idea desde el celular, Jarvis la **encola**, la ejecuta **autónomamente** dentro
del lab, reporta progreso y resultado, y vuelca aprendizajes a Obsidian.

### 7.1 Qué es una misión

Una unidad de trabajo autónoma con un objetivo en lenguaje natural ("corré un
recon completo de Metasploitable y anotá los puertos abiertos", "arrancá la prueba
de estrés de detección y avisame cada pase"). A diferencia de un turno de chat
normal (`/api/chat`, request→response inmediato), una misión **puede durar horas**,
corre en background, y sobrevive a que el celular se desconecte y se reconecte.

### 7.2 Estados de una misión

```
   encolada ──▶ corriendo ──▶ completada
                   │  ▲            
                   │  │           
                   ▼  │           
        necesita-confirmación     
        (pausada, esperando OK    
         de Damian para un paso   
         gated)                   
                   │              
                   ▼              
                fallida           
```

- **encolada** — aceptada, aún no empezó (p. ej. la PC estaba ocupada con otra
  misión; se procesan de a una para no pisar el uso de GPU/VM).
- **corriendo** — el agente está ejecutando pasos (VM control, SSH a Kali, tools
  de pentest, escritura al vault).
- **necesita-confirmación / pausada** — la misión llegó a un paso que cae en una
  categoría gated (§7.4). **Se detiene y espera**: no adivina, no asume el "sí".
  Manda al celular exactamente qué quiere hacer y por qué. Reanuda solo con OK
  explícito.
- **completada** — objetivo cumplido; el reporte final está en el vault y resumido
  al celular.
- **fallida** — error irrecuperable, timeout, o Damian la canceló. El motivo queda
  en el audit log y en el reporte.

### 7.3 Cómo fluye

1. Damian manda la idea desde el celular (por el mismo canal autenticado sobre
   Tailscale). Jarvis responde al toque *"misión #N encolada"* — no la ejecuta en
   el request; la mete en la cola. (Esto encaja con el WebSocket existente
   `/ws/phone` y el modelo 1:1 celular↔PC de `app/phone_link.py`, que ya sabe
   mantener una conexión viva y correlacionar mensajes por id.)
2. Un worker en background toma la misión y corre el loop del agente
   (`app/agent.py`) con las tools nuevas + existentes. Cada paso se audita.
3. Progreso: Jarvis empuja updates al celular ("recon terminado, 23 puertos",
   "snapshot POST tomado", "pase 2/5 de la prueba de detección"). Si el celular
   está desconectado, los updates se acumulan y se entregan al reconectar (la cola
   es la fuente de verdad del estado, no la conexión).
4. Al terminar: Jarvis escribe una **nota en el vault Obsidian** con los
   aprendizajes (usa las tools `obsidian_*` existentes; el vault ya distingue
   autoría jarvis/humano, tags y wikilinks) y manda al celular un resumen corto con
   el link a la nota.

### 7.4 Confirmaciones remotas para acciones gated

Cuando una misión autónoma llega a algo que requiere confirmación (§9), **no lo
hace y no lo saltea**: transiciona a `necesita-confirmación`, manda al celular la
descripción exacta de la acción (qué tool, qué argumentos, qué VM/target, por qué),
y espera un OK explícito. El OK viaja por el mismo canal autenticado.

Esto **reusa patrones que ya existen en el código**, no inventa un mecanismo de
consentimiento nuevo:

- Igual que el `preview_token` de un solo uso de `web_forms` ata un dry-run
  concreto a su submit (ver `app/config.py::form_preview_token_ttl_seconds` y
  `ESTADO.md`), la confirmación remota debería atar el OK a **esa** acción
  concreta (un id de paso, no un "sí" genérico reutilizable), con TTL corto: si
  pasan minutos, mejor re-pedir, porque el estado del lab pudo cambiar.
- Igual que `selfrepair` exige un `proposal_id` concreto que Damian confirma a
  mano para aplicar un fix, el paso gated de una misión exige la confirmación de
  *ese* paso identificado, no una autorización amplia.
- Y, no negociable: **ninguna confirmación remota puede ampliar
  `authorized_targets.yaml`**. Si el paso gated es "atacar una IP fuera de scope",
  la respuesta correcta no es "confirmar remoto" sino "rechazar": ese archivo solo
  se edita a mano en la PC (§9).

---

## 8. Requisito físico: la PC prendida

Toda esta capacidad vive **en la PC de casa**. Si la PC está apagada, no hay Jarvis
que orquestar: Tailscale, el backend, VirtualBox y las VMs corren ahí.

### 8.1 Escenario base: PC encendida (o en suspensión con la red viva)

El caso normal: Damian deja la PC prendida (o suspendida con Tailscale y la NIC
activas). El backend está levantado (o se levanta al boot), el nodo Tailscale está
online, y el celular llega sin más.

### 8.2 Opción Wake-on-LAN (encender la PC apagada)

**Wake-on-LAN (WoL)** permite encender la PC a distancia mandándole un "magic
packet" a la placa de red, que sigue escuchando aun con la PC apagada
([Windows Central — WoL en Windows 11](https://www.windowscentral.com/software-apps/windows-11/how-to-enable-wake-on-lan-on-windows-11)).
Cómo se configuraría (a mano, por Damian — nada de esto lo hace Jarvis):

1. **BIOS/UEFI:** habilitar WoL / "Power On By PCI-E" / "Wake on Magic Packet" en
   la sección de Power Management. Sin este paso, lo demás no sirve
   ([Deskin — WoL Windows 11 2026](https://deskin.io/resource/blog/wake-on-lan-windows-11)).
2. **Adaptador de red (Device Manager → NIC Ethernet):** en *Power Management*,
   tildar "Allow this device to wake the computer" y "Only allow a magic packet to
   wake the computer"; en *Advanced*, "Wake on Magic Packet" = Enabled.
3. **Desactivar Fast Startup** de Windows, que interfiere con WoL.
4. **Ethernet cableado**, no WiFi/USB (WoL por WiFi es poco confiable).

**El problema del "desde afuera de casa":** un magic packet es tráfico de capa 2
(broadcast en la LAN local); **no cruza internet ni el NAT del router** por sí
solo. Dos caminos realistas para dispararlo remotamente **sin abrir el router**:

- **Un segundo dispositivo siempre encendido en la LAN dentro del tailnet** (una
  Raspberry Pi, el router si corre Tailscale, otra maquinita) que reciba la orden
  de Jarvis/celular por Tailscale y **emita el magic packet en la LAN local**.
  Este relay es el patrón limpio: nada expuesto al exterior, WoL sigue siendo
  local.
- **Router con WoL/Tailscale integrado** que sepa despertar la PC bajo pedido.

### 8.3 Si la PC está apagada y no hay WoL

Degradación honesta: el celular no puede levantar nada. La app debería mostrar
"PC offline" (el health-check no responde) en vez de colgarse esperando. Damian
tendría que encenderla presencialmente o dejarla prendida antes de salir. WoL es
una **conveniencia opcional**, no un requisito del diseño; la fase 1–4 (§10)
funcionan perfectamente con la PC ya encendida.

---

## 9. Modelo de seguridad y amenazas (breve)

### 9.1 Qué protege cada capa

| Capa | Qué garantiza | Contra qué |
|------|----------------|------------|
| **Tailscale (WireGuard)** | Solo dispositivos del tailnet de Damian llegan al puerto; tráfico cifrado extremo a extremo; deny-by-default + grants (§3.3). | Internet abierta, sniffing en WiFi ajeno, escaneo/fuerza bruta desde afuera. |
| **Auth por dispositivo (token/JWT, DPAPI)** | Solo el celular con credencial válida y vigente opera; revocable sin afectar otros dispositivos (§4). | Un dispositivo comprometido/robado dentro del tailnet; secreto filtrado. |
| **Gates existentes** (`authorized_targets.yaml`, `dry-run→confirm`, `preview_token`, `proposal_id`, blocklist + audit, `FS_ALLOWED_ROOT`) | Ni el LLM ni el canal remoto pueden atacar fuera de scope, aplicar algo irreversible sin confirmación, ni escribir la lista de autorización (§5, §6, §7.4). | Errores/alucinaciones del modelo; una orden remota mal formada; un compromiso parcial que intente escalar. |
| **Aislamiento de red del lab** (`labnet` sin salida, §3 del range) | El tráfico ofensivo no sale del `10.13.37.0/24`. | Que un ataque "se escape" del lab hacia la LAN real o internet. |
| **Audit log firmado (Ed25519)** | Traza inalterable de qué hizo Jarvis en remoto. | Repudio / borrado de rastros; auditoría posterior. |

### 9.2 Qué NO cubre

- **Compromiso de la cuenta de Windows de Damian en la PC:** DPAPI ata los
  secretos a esa cuenta; si un atacante *ya es* esa cuenta, tiene acceso a lo
  mismo que Jarvis. Fuera de alcance de este diseño (es el supuesto de confianza
  base de toda la máquina).
- **Compromiso de la cuenta de Tailscale o del celular físico desbloqueado:** por
  eso el token por dispositivo es revocable (§4.3) y conviene bloqueo de pantalla
  fuerte en el celular. Tailscale + token reducen la ventana, no la eliminan.
- **`pc_run_command` no es un sandbox:** sigue siendo blocklist de texto (ver
  `ESTADO.md`, propuesta de sandboxing en contenedor pendiente). La orquestación
  remota **no** amplía lo que `pc_run_command` puede hacer; hereda su superficie
  tal cual. La mitigación barata pendiente (achicar `FS_ALLOWED_ROOT`) sigue
  siendo recomendable antes de operar mucho en remoto.

### 9.3 La regla, otra vez

**Las categorías peligrosas siempre requieren confirmación explícita de Damian,
aunque la sesión sea remota:**

- **Borrar datos** (archivos, VMs, snapshots BASE) → confirmación.
- **Mover dinero / ejecutar transacciones** → Jarvis no lo hace; lo pide a Damian
  (regla general del proyecto, no se automatiza jamás).
- **Cambiar config del sistema** (blocklist de `pc_command`: shutdown, format,
  bcdedit, etc.) → bloqueado por el blocklist; nada de remoto lo desbloquea.
- **Atacar un blanco fuera de scope** → rechazado por `authorized_targets.yaml`;
  ninguna confirmación remota lo autoriza. Solo Damian, a mano, en la PC.

"Extensión de Damian" llega hasta acá y no más: Jarvis puede hacer autónomamente
todo lo que sea seguro y reversible dentro del lab, y **se detiene a preguntar**
en el borde de lo irreversible o peligroso.

---

## 10. Plan de implementación por fases

De menor a mayor riesgo. Cada fase es útil por sí sola y no depende de que exista
la siguiente. **Criterio general de "listo": tests en verde (`cd backend &&
pytest`), auditoría registrando, y ningún gate existente debilitado.**

### Fase 1 — Tool `vm_control` local (§5)

Wrapper sobre `VBoxManage` con allow-list de VMs del lab, corriendo **solo en
local** (Damian en la PC, sin nada remoto todavía). Es el bloque de menor riesgo:
no toca la red, no abre nada, solo enciende/apaga/snapshotea VMs propias.

*Listo cuando:* Jarvis puede listar/encender (headless)/apagar/savestate y
tomar/restaurar/listar snapshots de las VMs del lab por su nombre; una VM fuera de
la allow-list se rechaza en el código; cada operación queda en el audit log
firmado; tests de la tool en verde.

### Fase 2 — Endpoint autenticado sobre Tailscale (§3, §4)

Atar el backend a la interfaz Tailscale (`tailscale serve` preferido, bind a la
IP de Tailscale como plan B), grant de tailnet celular↔PC solo-ese-puerto, y token
por dispositivo guardado con DPAPI. El celular llega a Jarvis desde afuera de casa,
por chat normal (`/api/chat`), sin misiones todavía.

*Listo cuando:* desde datos móviles, el celular alcanza `/api/health` y `/api/chat`
**solo** por Tailscale (verificado: el puerto NO responde por LAN/internet); un
token inválido/vencido/revocado se rechaza; el router sigue sin puertos abiertos;
`API_KEY` legacy sigue funcionando en local durante la transición.

### Fase 3 — Ejecución en guest por SSH (`ssh_guest`) (§6)

Interfaz de gestión Jarvis↔Kali (host-only o NAT+forward del 22), clave SSH
dedicada bajo DPAPI, y la tool `ssh_guest` con allow-list de hosts de gestión.
Jarvis lanza recon/escaneo/emulación **dentro de labnet** desde Kali, con los
blancos aún restringidos por `authorized_targets.yaml`.

*Listo cuando:* Jarvis corre un `nmap -sV` (u otra tool) contra un blanco del lab
*a través de Kali por SSH*; un blanco fuera de scope se rechaza igual (gate
intacto); labnet sigue sin ruta al host/LAN/internet (aislamiento verificado); cada
ejecución auditada.

### Fase 4 — Cola de misiones + confirmaciones remotas (§7)

Worker en background, estados de misión, updates al celular que sobreviven
desconexiones, escritura de aprendizajes al vault, y el gate de
`necesita-confirmación` con OK remoto atado a cada paso (estilo `preview_token` /
`proposal_id`). Es la fase de mayor riesgo (autonomía real desde afuera), por eso
va última, sobre las tres capas ya probadas.

*Listo cuando:* Damian encola una misión desde el celular estando fuera de casa,
Jarvis la corre autónomamente en el lab, empuja progreso, se **detiene** en un paso
gated y espera OK explícito (verificado que sin OK no avanza y que el OK es de un
solo uso), completa, y deja la nota en Obsidian con resumen al celular; una acción
peligrosa (§9.3) nunca se ejecuta sin confirmación; opcional WoL (§8) probado si
Damian lo quiere.

---

## Fuentes (verificación 2026-08-17)

- [Tailscale — Access control (deny-by-default, cifrado)](https://tailscale.com/kb/1393/access-control)
- [Tailscale Serve examples (listen on localhost, publicar en el tailnet, TLS)](https://tailscale.com/docs/reference/examples/serve)
- [Tailscale — Manage permissions using ACLs / grants](https://tailscale.com/docs/features/access-control/acls)
- [Tailscale — ACL policy examples (src/dst/puerto)](https://tailscale.com/docs/reference/examples/acls)
- [JWT refresh token rotation — best practices 2026](https://codecondo.com/jwt-refresh-token-rotation/)
- [LogRocket — JWT authentication best practices](https://blog.logrocket.com/jwt-authentication-best-practices/)
- [API Authentication Best Practices 2026 (rotación de secretos)](https://skycloak.io/blog/api-authentication-best-practices/)
- [Windows Central — How to enable Wake on LAN on Windows 11](https://www.windowscentral.com/software-apps/windows-11/how-to-enable-wake-on-lan-on-windows-11)
- [Deskin — Wake on LAN in Windows 11 (2026)](https://deskin.io/resource/blog/wake-on-lan-windows-11)

### Referencias internas del repo

- `lab/CYBER-RANGE-DESIGN.md` — topología de labnet, blancos, snapshots, conexión Jarvis→Kali→blancos.
- `lab/DETECCION-ESTRES-NOCTURNO.md` — bucle de detección/emulación que las misiones lanzan.
- `lab/RETOMAR-LAB.md` — estado real del range (VirtualBox 7.2.14, Kali, Metasploitable2, DHCP labnet).
- `backend/app/network/guardrail.py` — gate de `authorized_targets.yaml` (scope de pentest).
- `backend/app/config.py` — flags, `API_KEY`, `TLS_ENABLED`, `authorized_targets_path`, `form_preview_token_ttl_seconds`.
- `backend/app/auth.py` + `app/main.py` — auth Bearer actual, WebSocket `/ws/phone`.
- `backend/app/network_info.py` — detección de IP Tailscale, `TAILSCALE_RANGE`.
- `backend/app/forms/credential_store.py` + `app/investigation/keys.py` — patrón DPAPI.
- `backend/app/shell_exec.py` + `app/tools/pc_command.py` — núcleo de shell + blocklist + auditoría.
- `backend/app/phone_link.py` — WebSocket 1:1 celular↔PC.
