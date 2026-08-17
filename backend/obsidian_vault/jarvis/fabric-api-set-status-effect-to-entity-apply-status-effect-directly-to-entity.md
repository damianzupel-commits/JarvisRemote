---
author: jarvis
category: general
created: '2026-08-11T00:05:35.210175+00:00'
tags:
- investigacion
title: Fabric API set status effect to entity apply status effect directly to entity
updated: '2026-08-11T00:05:35.210175+00:00'
---

Investigación automática de Jarvis sobre "Fabric API set status effect to entity apply status effect directly to entity", basada en 4 página(s) reales visitadas.

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


### StatusEffect (yarn 22w03a+build.6 API)
Fuente: https://maven.fabricmc.net/docs/yarn-22w03a+build.6/net/minecraft/entity/effect/StatusEffect.html

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
Package net.minecraft.entity.effect
Class StatusEffect
java.lang.Object
net.minecraft.entity.effect.StatusEffect
Direct Known Subclasses:
AbsorptionStatusEffect, DamageModifierStatusEffect, HealthBoostStatusEffect, InstantStatusEffect
public class StatusEffect
extends Object
Mappings:
[...enlaces de navegación del sitio omitidos...]
private final Map<EntityAttribute,EntityAttributeModifier>
attributeModifiers
 
private final StatusEffectCategory
category
 
private final int
color
 
private @Nullable String
translationKey
 
[...enlaces de navegación del sitio omitidos...]
StatusEffect(StatusEffectCategory category, int color)
 
[...enlaces de navegación del sitio omitidos...]
addAttributeModifier(EntityAttribute attribute, String uuid, double amount, EntityAttributeModifier.Operation operation)
 
double
adjustModifierAmount(int amplifier, EntityAttributeModifier modifier)
 
void
applyInstantEffect(@Nullable Entity source, @Nullable Entity attacker, LivingEntity target, int amplifier, double proximity)
 
void
applyUpdateEffect(LivingEntity entity, int amplifier)
 
static @Nullable StatusEffect
byRawId(int rawId)
 
boolean
canApplyUpdateEffect(int duration, int amplifier)
 
Map<EntityAttribute,EntityAttributeModifier>
getAttributeModifiers()
 
StatusEffectCategory
getCategory()
 
int
getColor()
 
Text
getName()
 
static int
getRawId(StatusEffect type)
 
String
getTranslationKey()
 
boolean
isBeneficial()
 
boolean
isInstant()
 
protected String
loadTranslationKey()
 
void
onApplied(LivingEntity entity, AttributeContainer attributes, int amplifier)
 
void
onRemoved(LivingEntity entity, AttributeContainer attributes, int amplifier)
 
Methods inherited from class java.lang.Object
clone, equals, finalize, getClass, hashCode, notify, notifyAll, toString, wait, wait, wait
Field Details
attributeModifiers
private final Map<EntityAttribute,EntityAttributeModifier> attributeModifiers
Mappings:
Namespace	Name	Mixin selector
official	a	Lawq;a:Ljava/util/Map;
intermediary	field_5885	Lnet/minecraft/class_1291;field_5885:Ljava/util/Map;
named	attributeModifiers	Lnet/minecraft/entity/effect/StatusEffect;attributeModifiers:Ljava/util/Map;
category
private final StatusEffectCategory category
Mappings:
Namespace	Name	Mixin selector
official	b	Lawq;b:Lawr;
intermediary	field_18270	Lnet/minecraft/class_1291;field_18270:Lnet/minecraft/class_4081;
named	category	Lnet/minecraft/entity/effect/StatusEffect;category:Lnet/minecraft/entity/effect/StatusEffectCategory;
color
private final int color
Mappings:
Namespace	Name	Mixin selector
official	c	Lawq;c:I
intermediary	field_5886	Lnet/minecraft/class_1291;field_5886:I
named	color	Lnet/minecraft/entity/effect/StatusEffect;color:I
translationKey
@Nullable
private @Nullable String translationKey
Mappings:
Namespace	Name	Mixin selector
official	d	Lawq;d:Ljava/lang/String;
intermediary	field_58

### StatusEffect (yarn API)
Fuente: https://maven.fabricmc.net/docs/yarn-1.16.5+build.5/net/minecraft/entity/effect/StatusEffect.html

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
Package net.minecraft.entity.effect
Class StatusEffect
java.lang.Object
net.minecraft.entity.effect.StatusEffect
Direct Known Subclasses:
AbsorptionStatusEffect, DamageModifierStatusEffect, HealthBoostStatusEffect, InstantStatusEffect
public class StatusEffect
extends Object
Field Summary
Fields
Modifier and Type	Field	Description
private Map<EntityAttribute,​EntityAttributeModifier>	attributeModifiers	 
[...enlaces de navegación del sitio omitidos...]
protected	StatusEffect​(StatusEffectType type, int color)	 
Method Summary
All MethodsStatic MethodsInstance MethodsConcrete Methods
Modifier and Type	Method	Description
StatusEffect	addAttributeModifier​(EntityAttribute attribute, String uuid, double amount, EntityAttributeModifier.Operation operation)	 
double	adjustModifierAmount​(int amplifier, EntityAttributeModifier modifier)	 
void	applyInstantEffect​(Entity source, Entity attacker, LivingEntity target, int amplifier, double proximity)	 
void	applyUpdateEffect​(LivingEntity entity, int amplifier)	 
static StatusEffect	byRawId​(int rawId)	 
boolean	canApplyUpdateEffect​(int duration, int amplifier)	 
Map<EntityAttribute,​EntityAttributeModifier>	getAttributeModifiers()	 
int	getColor()	 
Text	getName()	 
static int	getRawId​(StatusEffect type)	 
String	getTranslationKey()	 
StatusEffectType	getType()	 
boolean	isBeneficial()	 
boolean	isInstant()	 
protected String	loadTranslationKey()	 
void	onApplied​(LivingEntity entity, AttributeContainer attributes, int amplifier)	 
void	onRemoved​(LivingEntity entity, AttributeContainer attributes, int amplifier)	 
Methods inherited from class java.lang.Object
clone, equals, finalize, getClass, hashCode, notify, notifyAll, toString, wait, wait, wait
Field Details
attributeModifiers
private final Map<EntityAttribute,​EntityAttributeModifier> attributeModifiers
[...enlaces de navegación del sitio omitidos...]
protected StatusEffect​(StatusEffectType type,
int color)
Method Details
byRawId
@Nullable
public static StatusEffect byRawId​(int rawId)
getRawId
public static int getRawId​(StatusEffect type)
applyUpdateEffect
public void applyUpdateEffect​(LivingEntity entity,
int amplifier)
applyInstantEffect
public void applyInstantEffect​(@Nullable
Entity source,
@Nullable
Entity attacker,
LivingEntity target,
int amplifier,
double proximity)
canApplyUpdateEffect
public boolean canApplyUpdateEffect​(int duration,
int amplifier)
isInstant
public boolean isInstant()
loadTranslationKey
protected String loadTranslationKey()
getTranslationKey
public String getTranslationKey()
getName
public Text getName()
getType
@Environment(CLIENT)
public StatusEffectType getType()
getColor
public int getColor()
addAttributeModifier
public StatusEffect addAttributeModifier​(EntityAttribute attribute,
String uuid,
double amount,
EntityAttributeModifier.Operation operation)
getAttributeModifiers

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

## Notas relacionadas
- [[Fabric mod development AttackEntityCallback apply status effect to entity]]
- [[Fabric mod development]]
- [[Fabric mod development sword status effect event AttackEntityCallback]]
- [[aplicar un efecto de estado (StatusEffect) al golpear un enemigo en un item custom de Fabric Minecraft]]
- [[Índice: general]]