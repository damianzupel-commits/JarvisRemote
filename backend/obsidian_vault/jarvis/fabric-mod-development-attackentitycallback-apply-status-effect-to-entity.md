---
author: jarvis
category: general
created: '2026-08-11T00:01:34.585153+00:00'
tags:
- investigacion
title: Fabric mod development AttackEntityCallback apply status effect to entity
updated: '2026-08-11T00:01:34.585153+00:00'
---

Investigación automática de Jarvis sobre "Fabric mod development AttackEntityCallback apply status effect to entity", basada en 4 página(s) reales visitadas.

## Fuentes

### Mob Effects | Fabric Documentation
Fuente: https://docs.fabricmc.net/develop/entities/effects

[...enlaces de navegación del sitio omitidos...]

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

[...enlaces de navegación del sitio omitidos...]
Mob Effects - NeoForge Docs (except Potions)
[...enlaces de navegación del sitio omitidos...]

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
[...enlaces de navegación del sitio omitidos...]

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
[...enlaces de navegación del sitio omitidos...]

Texture
​

The mob effect icon is a 18x18 PNG which will appear in the player's inventory screen. Place your custom icon in:

text
resources/assets/example-mod/textures/mob_effect/tater.png
Download Example Texture
Translations
​

Like any other translation, you can add an entry with ID format "effect.example-mod.effect-identifier": "Value" to the language file.

json
{
  "effect.example-mod.tater": "Tater"
}
1
2


### Adding Status Effects [Fabric Wiki]
Fuente: https://wiki.fabricmc.net/tutorial:status_effects

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

### Entity Attributes | Fabric Documentation
Fuente: https://docs.fabricmc.net/develop/entities/attributes

[...enlaces de navegación del sitio omitidos...]

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

[...enlaces de navegación del sitio omitidos...]
Attributes - NeoForge Docs (except Neo exclusives)
[...enlaces de navegación del sitio omitidos...]

Learn how to add custom attributes to entities.

Attributes determine the properties that your modded entity can possess. Using Fabric, you can create your own custom attributes that enhance gameplay mechanics and apply vanilla ones as well.

Creating a Custom Attribute
​

Let's create a custom attribute named AGGRO_RANGE. This attribute will control the distance an entity can detect and react to potential threats from.

Defining the Attribute Class
​

Begin by creating a Java class to manage the definition and registration of your attributes under your mod's code structure. This example will create the following functions in a class named ModAttributes.

First, start with a basic helper method to register your mod's attributes. This method will accept the following parameters and register an attribute.

[...enlaces de navegación del sitio omitidos...]
private static Holder<Attribute> register(
		String name, double defaultValue, double minValue, double maxValue, boolean syncedWithClient
) {
	Identifier identifier = Identifier.fromNamespaceAndPath(ExampleMod.MOD_ID, name);
	Attribute entityAttribute = new RangedAttribute(
			identifier.toLanguageKey(),
			defaultValue,
			minValue,
			maxValue
	).setSyncable(syncedWithClient);

	return Registry.registerForHolder(BuiltInRegistries.ATTRIBUTE, identifier, entityAttribute);
}
[...enlaces de navegación del sitio omitidos...]


We'll then register an attribute named AGGRO_RANGE with the name aggro_range, a default value of 8.0, a minimum value of 0, and a maximum value set as high as it can be. This attribute will not be synced to players.

java
public static final Holder<Attribute> AGGRO_RANGE = register(
		"aggro_range",
		8.0,
		0.0,
		Double.MAX_VALUE,
		false
);
[...enlaces de navegación del sitio omitidos...]

Translating Custom Attributes
​

To display the attribute name in a human-readable format, you must modify assets/example-mod/lang/en_us.json to include:

json
{
  "attribute.name.example-mod.aggro_range": "Aggro Range"
}
1
2
3

Initialization
​

To make sure the attribute is registered properly, you'll need to ensure it is initialized during mod startup. This can be done by adding a public static initialize method to your class and call it from your mod's initializer class. Currently, this method doesn't need anything inside it.

java
public static void initialize() {
}
1
2

java
public class ExampleModAttributes implements ModInitializer {
	@Override
	public void onInitialize() {
		ModAttributes.initialize();
	}
}
[...enlaces de navegación del 

### AttackEntityCallback (fabric-api 0.32.5+1.16 API)
Fuente: https://maven.fabricmc.net/docs/fabric-api-0.32.5+1.16/net/fabricmc/fabric/api/event/player/AttackEntityCallback.html

[...enlaces de navegación del sitio omitidos...]
SUMMARY: 
NESTED | 
FIELD | 
CONSTR | 
METHOD
DETAIL: 
FIELD | 
CONSTR | 
METHOD
SEARCH:  
Package net.fabricmc.fabric.api.event.player
Interface AttackEntityCallback
public interface AttackEntityCallback
Callback for left-clicking ("attacking") an entity. Is hooked in before the spectator check, so make sure to check for the player's game mode as well!

Upon return:

SUCCESS cancels further processing and, on the client, sends a packet to the server.
PASS falls back to further processing.
FAIL cancels further processing and does not send a packet to the server.
Field Summary
Fields
Modifier and Type	Field	Description
static Event<AttackEntityCallback>	EVENT	 
Method Summary
All MethodsInstance MethodsAbstract Methods
Modifier and Type	Method	Description
net.minecraft.util.ActionResult	interact​(net.minecraft.entity.player.PlayerEntity player, net.minecraft.world.World world, net.minecraft.util.Hand hand, net.minecraft.entity.Entity entity, @Nullable net.minecraft.util.hit.EntityHitResult hitResult)	 
Field Details
EVENT
static final Event<AttackEntityCallback> EVENT
Method Details
interact
net.minecraft.util.ActionResult interact​(net.minecraft.entity.player.PlayerEntity player,
net.minecraft.world.World world,
net.minecraft.util.Hand hand,
net.minecraft.entity.Entity entity,
@Nullable
@Nullable net.minecraft.util.hit.EntityHitResult hitResult)
[...enlaces de navegación del sitio omitidos...]
SUMMARY: 
NESTED | 
FIELD | 
CONSTR | 
METHOD
DETAIL: 
FIELD | 
CONSTR | 
METHOD

## Notas relacionadas
- [[Fabric mod development sword status effect event AttackEntityCallback]]
- [[aplicar un efecto de estado (StatusEffect) al golpear un enemigo en un item custom de Fabric Minecraft]]
- [[Fabric mod development]]
- [[Fabric API sistema de eventos: AttackEntityCallback UseItemCallback UseBlockCallback ServerTickEvents PlayerBlockBreakEvents]]
- [[registrar un item custom en Fabric Minecraft con Identifier y namespace del mod]]
- [[Índice: general]]