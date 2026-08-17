"""Referencia curada y verificada de Fabric API/Loom para inyectar en tareas
de `opencode_run_task` (app/tools/opencode.py) sobre mods de Minecraft --
diseño 2026-08-12, mismo patrón que `app/security/triage_reference.py`
(lookup determinístico de conocimiento de dominio, no depender de la memoria
del modelo), pero para código en vez de seguridad.

Motivo real: DOS intentos distintos (v6 del propio loop de Jarvis, y el
primer intento de `opencode_run_task`) inventaron por separado la clase del
evento de ataque -- v6 usó una API inventada "alrededor" de un uso
correcto en espíritu de AttackEntityCallback; OpenCode inventó directamente
`net.fabricmc.fabric.api.event.enterprise.v1.EntityAttackEntityCallback`
(un paquete "enterprise" que no existe) con una firma de método también
inventada. Ningún modelo local (jarvis-text-v2) tiene esto memorizado
correctamente.

Cada dato de abajo fue verificado contra FUENTE REAL antes de escribirse acá
(no copiado de memoria ni de una página de docs sin cruzar):
- AttackEntityCallback: código fuente real de
  github.com/FabricMC/fabric, rama 1.21, fabric-events-interaction-v0
  (net/fabricmc/fabric/api/event/player/AttackEntityCallback.java) --
  paquete, EVENT, y firma exacta de interact() confirmados letra por letra.
- fabric.mod.json: docs.fabricmc.net/develop/loader/fabric-mod-json
  (spec oficial).
- gradle.properties/build.gradle con fabric-loom: DeepWiki de
  FabricMC/fabric-example-mod, sección "Gradle Configuration" (estructura
  real del template oficial).
- Item/SwordItem/StatusEffect: conocimiento de modding estable (Item.Settings
  reemplazó a FabricItemSettings hace varias versiones; StatusEffects.POISON
  es un campo vanilla estable) -- MENOS verificado letra-por-letra que lo de
  arriba porque no hubo tiempo de cruzar cada firma contra fuente real, así
  que el texto lo marca explícitamente como "si un error de compilación
  apunta acá, investigá con research_topic antes de adivinar".

TODO: mappings de Yarn, no Mojang (mojmap) -- este proyecto especifica
`yarn_mappings` en gradle.properties (ver REFERENCE de abajo), así que los
nombres de clase son los de Yarn (PlayerEntity, World, Hand, ActionResult,
Identifier), NO los de Mojang (Player, Level, InteractionHand,
InteractionResult, ResourceLocation) -- mezclar los dos mapeos en el mismo
proyecto no compila. Esta es la confusión real que causó ambigüedad al armar
esta referencia (algunas páginas de docs de Fabric muestran ejemplos en
mojmap): se resolvió a favor de Yarn porque es lo que gradle.properties de
este proyecto declara.
"""

from __future__ import annotations

FABRIC_MOD_REFERENCE = """--- Referencia curada de Fabric API (Minecraft 1.21.x, Yarn mappings) ---
Esta referencia es TEXTO VERIFICADO contra fuente real, no memoria del modelo.
Si necesitás una clase/método que NO aparece acá, usá research_topic para
buscarlo en vez de inventar un nombre plausible -- dos intentos previos de
generar este mismo mod fallaron exactamente por inventar la clase del evento
de ataque.

IMPORTANTE: este proyecto usa YARN mappings (no Mojang/mojmap). Los nombres
de clase son PlayerEntity, World, Hand, ActionResult, Identifier -- NO Player,
Level, InteractionHand, InteractionResult, ResourceLocation (esos son mojmap,
NO compilan con Yarn).

IMPORTANTE (rutas de archivo): cuando escribas un archivo, usá SIEMPRE una
ruta RELATIVA al directorio del proyecto (ej. "settings.gradle",
"src/main/java/com/example/PoisonedSwordMod.java") -- NUNCA una ruta que
empiece con "/" (ej. "/settings.gradle"). Un "/" al principio se resuelve
como la raíz del disco (C:\\), no como la raíz del proyecto, y ahí no tenés
permiso de escritura -- eso hace fallar CADA escritura con un error opaco.
Esto ya pasó en un intento real anterior de este mismo mod.

## 1. Evento de ataque a entidad (AttackEntityCallback)
Paquete y firma EXACTOS (verificados contra el código fuente real de
FabricMC/fabric, rama 1.21):

```java
package net.fabricmc.fabric.api.event.player;

import net.fabricmc.fabric.api.event.Event;
import net.minecraft.entity.Entity;
import net.minecraft.entity.player.PlayerEntity;
import net.minecraft.util.ActionResult;
import net.minecraft.util.Hand;
import net.minecraft.util.hit.EntityHitResult;
import net.minecraft.world.World;

public interface AttackEntityCallback {
    Event<AttackEntityCallback> EVENT = ...; // ya registrado por fabric-api, no lo redefinas

    ActionResult interact(PlayerEntity player, World world, Hand hand, Entity entity, @Nullable EntityHitResult hitResult);
}
```

Uso real (registrar un listener):
```java
AttackEntityCallback.EVENT.register((player, world, hand, entity, hitResult) -> {
    if (player.getStackInHand(hand).isOf(MyItems.POISONED_SWORD) && entity instanceof LivingEntity livingEntity) {
        livingEntity.addStatusEffect(new StatusEffectInstance(StatusEffects.POISON, 100, 0));
    }
    return ActionResult.PASS;
});
```
NO existe ninguna clase "EntityAttackEntityCallback" ni ningún paquete
"event.enterprise" en Fabric API -- si ves esos nombres en un borrador, es
una alucinación, no una API real.

## 2. Aplicar un StatusEffect (veneno) a una entidad
```java
import net.minecraft.entity.LivingEntity;
import net.minecraft.entity.effect.StatusEffectInstance;
import net.minecraft.entity.effect.StatusEffects;

livingEntity.addStatusEffect(new StatusEffectInstance(StatusEffects.POISON, durationTicks, amplifier));
```
`StatusEffects.POISON` es un campo vanilla estable. `durationTicks` es en
ticks (20 ticks = 1 segundo real). `amplifier` 0 = nivel I.

## 3. Registrar un item custom (espada)
`FabricItemSettings` está DEPRECADO/eliminado en versiones recientes -- usar
`Item.Settings` directo (Fabric API ya lo extiende con lo necesario):
```java
import net.minecraft.item.Item;
import net.minecraft.item.SwordItem;
import net.minecraft.item.ToolMaterials; // o el sistema de ToolMaterial real de esta version
import net.minecraft.registry.Registries;
import net.minecraft.registry.Registry;
import net.minecraft.util.Identifier;

public static final Item POISONED_SWORD = Registry.register(
    Registries.ITEM,
    Identifier.of(MOD_ID, "poisoned_sword"),
    new SwordItem(ToolMaterials.IRON, new Item.Settings().attributeModifiers(SwordItem.createAttributeModifiers(ToolMaterials.IRON, 3, -2.4f)))
);
```
NOTA DE INCERTIDUMBRE: el constructor exacto de SwordItem y de
ToolMaterials/ToolMaterial cambió varias veces entre versiones de Minecraft
(1.20 vs 1.21 no son idénticos acá) -- si `./gradlew build` falla apuntando a
esta clase, usá research_topic con la versión exacta de Minecraft del
proyecto antes de seguir adivinando parámetros.

## 4. fabric.mod.json (spec real, docs.fabricmc.net)
Campos obligatorios: `schemaVersion` (siempre 1, primer campo), `id`
(2-64 caracteres, letras/dígitos/guión/guión bajo), `version`. Campos
comunes: `name`, `description`, `authors`, `contact`, `license`,
`environment` ("*"/"client"/"server"), `entrypoints` (`main` para
ModInitializer, `client` para ClientModInitializer), `depends`.
```json
{
  "schemaVersion": 1,
  "id": "poisoned_sword_mod",
  "version": "1.0.0",
  "name": "Poisoned Sword Mod",
  "environment": "*",
  "entrypoints": { "main": ["com.example.poisonedsword.PoisonedSwordMod"] },
  "depends": { "fabricloader": ">=0.16.0", "minecraft": "~1.21.x", "fabric-api": "*" }
}
```

## 5. Estructura real de Gradle (fabric-loom) -- verificado contra el
template oficial FabricMC/fabric-example-mod
`build.gradle`:
```gradle
plugins {
    id 'fabric-loom' version '1.10-SNAPSHOT'
    id 'maven-publish'
}

dependencies {
    minecraft "com.mojang:minecraft:${project.minecraft_version}"
    mappings "net.fabricmc:yarn:${project.yarn_mappings}:v2"
    modImplementation "net.fabricmc:fabric-loader:${project.loader_version}"
    modImplementation "net.fabricmc.fabric-api:fabric-api:${project.fabric_version}"
}
```
`gradle.properties`:
```properties
org.gradle.jvmargs=-Xmx1G
org.gradle.parallel=true

minecraft_version=1.21.1
yarn_mappings=1.21.1+build.1
loader_version=0.16.10
fabric_version=0.119.5+1.21.1

mod_version=1.0.0
maven_group=com.example
archives_base_name=poisoned-sword-mod
```
`settings.gradle` SOLO define el nombre del proyecto y los repos de plugins
-- NO lleva bloques `dependencies{}` (esos van en build.gradle, nunca en
settings.gradle):
```gradle
pluginManagement {
    repositories {
        maven { url = "https://maven.fabricmc.net/" }
        gradlePluginPortal()
    }
}
rootProject.name = "poisoned-sword-mod"
```
El Gradle wrapper (`gradlew`/`gradlew.bat`/`gradle/wrapper/gradle-wrapper.jar`)
tiene que ser el JAR BINARIO real generado por `gradle wrapper` -- un archivo
de texto con ese nombre no sirve, `./gradlew` va a fallar inmediatamente. Si
no podés generar el binario real, mejor no crear el archivo y documentar en
el README que hace falta correr `gradle wrapper` a mano, en vez de dejar un
placeholder que parece un wrapper real pero no lo es.
--- fin de la referencia curada ---"""
