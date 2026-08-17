---
author: jarvis
category: desarrollo-de-juegos
created: '2026-08-10T16:46:00.677720+00:00'
tags:
- investigacion
title: registrar un item custom en Fabric Minecraft con Identifier y namespace del
  mod
updated: '2026-08-10T16:46:00.677720+00:00'
---

Investigación automática de Jarvis sobre "registrar un item custom en Fabric Minecraft con Identifier y namespace del mod", basada en 3 página(s) reales visitadas.

## Fuentes

### Adding an Item [Fabric Wiki]
Fuente: https://wiki.fabricmc.net/tutorial:items

skip to content
Fabric Wiki
User Tools
Register
Log In
Site Tools
Search
Recent ChangesSitemap
Trace: • Adding an Item

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
Creating a Custom Projectile
Fluid

### Creating Your First Item | Fabric Documentation
Fuente: https://docs.fabricmc.net/develop/items/first-item

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
Creating Your First Item

Custom Food

Custom Potions

Custom Spawn Eggs

Custom Tools

Custom Armor

Item Models

Item Appearance

Custom Creative Tabs

Custom Item Interactions

Custom Enchantment Effects

Custom Data Components

Blocks
Fluids
Entities
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
Preparing Your Item IDs Class
Preparing Your Items Class
Registering an Item
Adding the Item to a Creative Tab
Naming The Item
Adding a Client Item, Texture and Model
Adding a Texture
Adding a Model
Breaking Down the Model JSON
Creating the Client Item
Breaking Down the Client Item JSON
Making the Item Compostable or a Fuel
Adding a Basic Crafting Recipe
Custom Tooltips
PAGE AUTHORS
FILES REFERENCED
ModItemIds.java
ModItems.java
ExampleModItems.java
item/suspicious_substance.json
items/suspicious_substance.json
LightningStick.java
Creating Your First Item 26.2
​

Learn how to register a simple item and how to texture, model and name it.

This page will introduce you into some key concepts relating to items, and how you can register, texture, model and name them.

If you aren't aware, everything in Minecraft is stored in registries, and items are no exception to that.

Preparing Your Item IDs Class
​

We'll start by creating a class that holds the name of our item, stored as a ResourceKey. A ResourceKey holds the name of the mod, the name of the item, and what registry it is for.

We'll implement a helper method that creates a ResourceKey given an item's name; it will fill in the rest of the data with constants, like the item registry and the mod's ID.

These references to the item are used for data-generating item tags.

You can put this method in a class called ModItemIds (or whatever you want to name the class).

TIP

Mojang does this with their items as well! Check out the ItemIds class for inspiration.

java
public class ModItemIds {
	public static ResourceKey<Item> create(String name) {
		// Create the item key.
		return ResourceKey.create(Registries.ITEM, Identifier.fromNamespaceAndPath(ExampleMod.MOD_ID, name));
	}
}
1
2
3
4
5
6

Preparing Your Items Class
​

To simplify the registering of items, you can create a method that accepts a resource key, some item properties, and a factory to create the Item instance.

This method will create an item with the provided key and register it with the game's item registry.

You can put this method in a class called ModItems (or whatever you want to name the class).

Mojang does this with their items as well! Check out the Items class for inspiration.

java
public class ModItems {
	public static Item register(ResourceKey<Item> itemKey, Func

### Intro to Registries [Fabric Wiki]
Fuente: https://wiki.fabricmc.net/tutorial:registry

skip to content
Fabric Wiki
User Tools
Register
Log In
Site Tools
Search
Recent ChangesSitemap
Trace: • Adding an Item • Intro to Registries

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
Creating a C

## Notas relacionadas
- [[estructura de un mod Fabric para Minecraft: build.gradle, fabric.mod.json y entrypoint]]
- [[Reporte de auditoría -- saas-boilerplate -- 2026-07-29]]
- [[Reporte de auditoría -- httpie-cli -- 2026-07-29]]
- [[Reporte de auditoría -- SuperSaaSFastAPI -- 2026-07-29]]
- [[Herramientas SAST y SCA - Resumen]]
- [[Índice: desarrollo-de-juegos]]