---
author: jarvis
category: desarrollo-de-juegos
created: '2026-08-10T16:46:41.231652+00:00'
tags:
- investigacion
title: aplicar un efecto de estado (StatusEffect) al golpear un enemigo en un item
  custom de Fabric Minecraft
updated: '2026-08-10T16:46:41.231652+00:00'
---

Investigación automática de Jarvis sobre "aplicar un efecto de estado (StatusEffect) al golpear un enemigo en un item custom de Fabric Minecraft", basada en 3 página(s) reales visitadas.

## Fuentes

### Mob Effects | Fabric Documentation
Fuente: https://docs.fabricmc.net/develop/entities/effects

Skip to content
Fabric Documentation
Search
Main Navigation
Home
Contribute
Code
Sidebar Navigation
Developer Guides

Creating a Project

Project Structure

Setting Up Your IDE

Opening a Project

Launching the Game

Generating Sources

Building a Mod

IDE Tips and Tricks

Items
Blocks
Fluids
Entities

Creating Your First Entity

Attributes

Mob Effects

Damage Types

Sounds
Commands
Recipes
Rendering
Data Generation
Serialization
Loom
Loader
Porting
Mixins
Class Tweakers
Miscellaneous Pages
On this page
Custom Mob Effects
Extend MobEffect
Registering Your Custom Effect
Texture
Translations
Applying The Effect
PAGE AUTHORS
SOURCES & RESOURCES
Mob Effects - NeoForge Docs (except Potions)
FILES REFERENCED
TaterEffect.java
ExampleModEffects.java
Unreferenced.java
Mob Effects 26.2
​

Learn how to add custom mob effects.

Mob effects, also known as status effects or simply effects, are a condition that can affect an entity. They can be positive, negative or neutral in nature. The base game applies these effects in various ways such as food, potions etc.

The /effect command can be used to apply effects on an entity.

Custom Mob Effects
​

In this tutorial we'll add a new custom effect called Tater which gives you one experience point every game tick.

Extend MobEffect
​

Let's create a custom effect class by extending MobEffect, which is the base class for all effects.

java
public class TaterEffect extends MobEffect {
	protected TaterEffect() {
		// category: StatusEffectCategory - describes if the effect is helpful (BENEFICIAL), harmful (HARMFUL) or useless (NEUTRAL)
		// color: int - Color is the color assigned to the effect (in RGB)
		super(MobEffectCategory.BENEFICIAL, 0xe9b8b3);
	}

	// Called every tick to check if the effect can be applied or not
	@Override
	public boolean shouldApplyEffectTickThisTick(int duration, int amplifier) {
		// In our case, we just make it return true so that it applies the effect every tick
		return true;
	}

	// Called when the effect is applied.
	@Override
	public boolean applyEffectTick(ServerLevel level, LivingEntity entity, int amplifier) {
		if (entity instanceof Player) {
			((Player) entity).giveExperiencePoints(1 << amplifier); // Higher amplifier gives you experience faster
		}

		return super.applyEffectTick(level, entity, amplifier);
	}
}
1
2
3
4
5
6
7
8
9
10
11
12
13
14
15
16
17
18
19
20
21
22
23
24

Registering Your Custom Effect
​

Similar to block and item registration, we use Registry.register to register our custom effect into the MOB_EFFECT registry. This can be done in our initializer.

java
public class ExampleModEffects implements ModInitializer {
	public static final Holder<MobEffect> TATER =
			Registry.registerForHolder(BuiltInRegistries.MOB_EFFECT, Identifier.fromNamespaceAndPath(ExampleMod.MOD_ID, "tater"), new TaterEffect());

	@Override
	public void onInitialize() {
		// ...
	}
}
1
2
3
4
5
6
7
8
9

Texture
​

The mob effect icon is a 18x18 PNG which will appear in the player's inventory 

### Adding Status Effects [Fabric Wiki]
Fuente: https://wiki.fabricmc.net/tutorial:status_effects

skip to content
Fabric Wiki
User Tools
Register
Log In
Site Tools
Search
Recent ChangesSitemap
Trace: • Adding Status Effects

← Go back to the homepage

Fabric Tutorials
Information On Tutorials
Basics
Introduction to Fabric and Modding (older version)
Setting up a Development Environment (older version)
Reading the Minecraft source
Modding with Fabric with Kotlin
Basic Conventions and Terminology
Server and Client Side
Introduction to Registries
Standard Registries
Applying Changes without Restarting Minecraft
Creating a language file
Items

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

Getting started using Data Generation
Advancements Generation
Loot Table Generation
Model Generation
Bucket Texture Data Generation
Tag Generation
Recipe Generation
Language File Generation
World Generation
Dimension Concepts
Generating Custom Ores
Adding Features
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
Creating a Custom Projectil

### Reddit - Prove your humanity
Fuente: https://www.reddit.com/r/MinecraftCommands/comments/w5lzk1/is_it_possible_to_inflict_status_effects_when_hit/

Prove your humanity

We’re committed to safety and security. But not for bots. Complete the challenge below and let us know you’re a real person.

Reddit, Inc. © "2026". All rights reserved.
User Agreement
Privacy Policy
Content Policy
Help

## Notas relacionadas
- [[registrar un item custom en Fabric Minecraft con Identifier y namespace del mod]]
- [[Índice: desarrollo-de-juegos]]
- [[estructura de un mod Fabric para Minecraft: build.gradle, fabric.mod.json y entrypoint]]
- [[Cómo Jarvis Repara Hallazgos de Seguridad Sin Perder el Foco]]
- [[Segmentacion de red y VLANs para seguridad]]