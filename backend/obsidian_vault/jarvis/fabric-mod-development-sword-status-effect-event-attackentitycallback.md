---
author: jarvis
category: general
created: '2026-08-10T23:57:11.552219+00:00'
tags:
- investigacion
title: Fabric mod development sword status effect event AttackEntityCallback
updated: '2026-08-10T23:57:11.552219+00:00'
---

Investigación automática de Jarvis sobre "Fabric mod development sword status effect event AttackEntityCallback", basada en 4 página(s) reales visitadas.

## Fuentes

### Event Index [Fabric Wiki]
Fuente: https://wiki.fabricmc.net/tutorial:event_index

[...enlaces de navegación del sitio omitidos...]

← Go back to the homepage

Fabric Tutorials
Information On Tutorials
Basics
Introduction to Fabric and Modding (older version)
Setting up a Development Environment (older version)
[...enlaces de navegación del sitio omitidos...]

Creation of items, such as tools, armor and food. Alongside crafting recipes and enchantments.

Creating Your First Item (older version)
Custom Item Tooltips
Creating Item Groups/Creative Tabs (older version)
Adding a Crafting Recipe
Custom Armor (older version)
Adding an Armor Trim
Custom Tools (older version)
Adding a Shield (1.21.5 and below)
Custom Enchantments (older version)
Transparency and Tinting (older version)
Adding Model Predicate Providers (before 1.21.4)
Blocks and Block Entities

Creation of blocks, storage of items and data in blocks via block entities, and the creation of models and blockstates.

Creating Your First Block
Block States
Making a Directional Block
Make the Block Waterloggable
Adding a BlockEntity (older version)
Modify BlockEntity data
Sync BlockEntity data with ItemStack
Block Containers (older version)
Transparency and Tinting (older version)
Rendering Blocks and Items Dynamically
Rendering Blocks and Items Dynamically using a custom Model
Rendering Blocks and Items Dynamically using Block Entity Renderers (older version)
Containers (older version)
Syncing Custom Data with Extended ScreenHandlers
Syncing Integers with PropertyDelegates
Adding a Custom Crop
Data Generation

The Fabric Data Generation API, which generates JSON files through data generators.

[...enlaces de navegación del sitio omitidos...]
Adding Trees (Advanced)
Adding structures (vanilla tutorial in Minecraft Wiki)
Adding Biomes (vanilla tutorial)
Adding Biomes (before 1.18)
Custom Chunk Generators (DRAFT)
Adding World Presets
Adding Dimensions (vanilla tutorial)
Creating a Custom Portal
Commands

Using Mojang's Brigadier library to create commands with complex arguments and actions.

Creating Commands (older version)
Command Exceptions
Command Suggestions (older version)
Command Redirects
Command Argument Types (older version)
Command Examples
Events

Using the many events included in Fabric API, and creating your own events for you or other mods to use.

Listening to Events (older version)
Creating Custom Events (older version)
Adding Items to Existing Loot Tables
Event Index (DRAFT)
Entities
Adding an Entity (older version)
Adding a Custom Spawn Egg (older version)
Creating a Custom Projectile
Fluids
Creating a Fluid (older version)
Mixins & ASM

The usage of SpongePowered's Mixin library, which is a highly complex topic. We recommend you read these pages thoroughly.

Introduction
Intro to Java Bytecode (Docs)
[...enlaces de navegación del sitio omitidos...]
Tips (WIP)
Examples
Hotswapping Mixins
Exporting and Dumping Mixin Targets
Access Widening (Old Page)
Reflection
Interface Injection (Old Page)
[...enlaces de navegación del sitio omitidos...]
Saved Data (older ver

### AttackEntityCallback (fabric-api 0.149.1+26.2 API)
Fuente: https://maven.fabricmc.net/docs/fabric-api-0.149.1+26.2/net/fabricmc/fabric/api/event/player/AttackEntityCallback.html

[...enlaces de navegación del sitio omitidos...]
interact(Player, Level, InteractionHand, Entity, EntityHitResult)
Interface AttackEntityCallback
public interface AttackEntityCallback
Callback for left-clicking ("attacking") an entity. Is hooked in before the spectator check, so make sure to check for the player's game mode as well!

Upon return:

SUCCESS cancels further processing and, on the client, sends a packet to the server.
PASS falls back to further processing.
FAIL cancels further processing and does not send a packet to the server.
Field Summary 
Fields
Modifier and Type
Field
Description
static final Event<AttackEntityCallback>
EVENT
 
[...enlaces de navegación del sitio omitidos...]
interact(net.minecraft.world.entity.player.Player player, net.minecraft.world.level.Level level, net.minecraft.world.InteractionHand hand, net.minecraft.world.entity.Entity entity, @Nullable net.minecraft.world.phys.EntityHitResult hitResult)
 
Field Details 
EVENT 
static final Event<AttackEntityCallback> EVENT
Method Details 
interact 
net.minecraft.world.InteractionResult interact(net.minecraft.world.entity.player.Player player,
 net.minecraft.world.level.Level level,
 net.minecraft.world.InteractionHand hand,
 net.minecraft.world.entity.Entity entity,
 @Nullable net.minecraft.world.phys.EntityHitResult hitResult)

### AttackEntityCallback (fabric-api 0.142.3+26.1 API)
Fuente: https://maven.fabricmc.net/docs/fabric-api-0.142.3+26.1/net/fabricmc/fabric/api/event/player/AttackEntityCallback.html

[...enlaces de navegación del sitio omitidos...]
interact(Player, Level, InteractionHand, Entity, EntityHitResult)
Interface AttackEntityCallback
public interface AttackEntityCallback
Callback for left-clicking ("attacking") an entity. Is hooked in before the spectator check, so make sure to check for the player's game mode as well!

Upon return:

SUCCESS cancels further processing and, on the client, sends a packet to the server.
PASS falls back to further processing.
FAIL cancels further processing and does not send a packet to the server.
Field Summary 
Fields
Modifier and Type
Field
Description
static final Event<AttackEntityCallback>
EVENT
 
[...enlaces de navegación del sitio omitidos...]
interact(net.minecraft.world.entity.player.Player player, net.minecraft.world.level.Level level, net.minecraft.world.InteractionHand hand, net.minecraft.world.entity.Entity entity, @Nullable net.minecraft.world.phys.EntityHitResult hitResult)
 
Field Details 
EVENT 
static final Event<AttackEntityCallback> EVENT
Method Details 
interact 
net.minecraft.world.InteractionResult interact(net.minecraft.world.entity.player.Player player,
 net.minecraft.world.level.Level level,
 net.minecraft.world.InteractionHand hand,
 net.minecraft.world.entity.Entity entity,
 @Nullable net.minecraft.world.phys.EntityHitResult hitResult)

### Events | Fabric Documentation
Fuente: https://docs.fabricmc.net/develop/events

[...enlaces de navegación del sitio omitidos...]

Creating a Project

Project Structure

Setting Up Your IDE

Opening a Project

Launching the Game

Generating Sources

Building a Mod

IDE Tips and Tricks

[...enlaces de navegación del sitio omitidos...]

Automated Testing

Debugging Mods

Events

Game Rules

Key Mappings

Networking

Resource Conditions

Statistics

Text and Translations

[...enlaces de navegación del sitio omitidos...]

A guide for using events provided by the Fabric API.

Fabric API provides a system that allows mods to react to actions or occurrences, also defined as events that occur in the game.

Events are hooks that satisfy common use cases and/or provide enhanced compatibility and performance between mods that hook into the same areas of the code. The use of events often substitutes the use of mixins.

Fabric API provides events for important areas in the Minecraft codebase that multiple modders may be interested in hooking into.

Events are represented by instances of net.fabricmc.fabric.api.event.Event which stores and calls callbacks. Often there is a single event instance for a callback, which is stored in a static field EVENT of the callback interface, but there are other patterns as well. For example, ClientTickEvents groups several related events together.

Callbacks
​

Callbacks are a piece of code that is passed as an argument to an event. When the event is triggered by the game, the passed piece of code will be executed.

Callback Interfaces
​

Each event has a corresponding callback interface. Callbacks are registered by calling register() method on an event instance, with an instance of the callback interface as the argument.

Listening to Events
​

This example registers an AttackBlockCallback to damage the player when they hit blocks that don't drop an item when hand-mined.

java
AttackBlockCallback.EVENT.register((player, level, hand, pos, direction) -> {
	BlockState state = level.getBlockState(pos);

	// Manual spectator check is necessary because AttackBlockCallbacks fire before the spectator check
	if (!player.isSpectator() && player.getMainHandItem().isEmpty() && state.requiresCorrectToolForDrops() && level instanceof ServerLevel serverLevel) {
		player.hurtServer(serverLevel, level.damageSources().generic(), 1.0F);
	}

	return InteractionResult.PASS;
});
[...enlaces de navegación del sitio omitidos...]

Adding Items to Existing Loot Tables
​

Sometimes you may want to add items to loot tables. For example, adding your drops to a vanilla block or entity.

The simplest solution, replacing the loot table file, can break other mods. What if they want to change them as well? We'll take a look at how you can add items to loot tables without overriding the table.

We'll be adding eggs to the coal ore loot table.

Listening to Loot Table Loading
​

Fabric API has an event that is fired when loot tables are loaded, LootTableEvents.MODIFY. You can register a callback for it in your mod's initializer. Let's also

## Notas relacionadas
- [[aplicar un efecto de estado (StatusEffect) al golpear un enemigo en un item custom de Fabric Minecraft]]
- [[Fabric mod development]]
- [[Fabric API sistema de eventos: AttackEntityCallback UseItemCallback UseBlockCallback ServerTickEvents PlayerBlockBreakEvents]]
- [[registrar un item custom en Fabric Minecraft con Identifier y namespace del mod]]
- [[Índice: desarrollo-de-juegos]]
- [[Índice: general]]