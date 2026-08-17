---
author: jarvis
category: general
created: '2026-08-10T19:31:51.848639+00:00'
tags:
- investigacion
title: Fabric mod development
updated: '2026-08-10T19:31:51.848639+00:00'
---

Investigación automática de Jarvis sobre "Fabric mod development", basada en 4 página(s) reales visitadas.

## Fuentes

### Fabric | The home of the Fabric mod development toolchain.
Fuente: https://fabricmc.net/

Fabric
 
Download Blog Develop Discuss Docs
Fabric Loader

Fabric is a modular, lightweight mod loader for Minecraft


Download
Play

The Fabric Loader download above is the bare minimum. Combine it with Fabric API to get all the important extra APIs mods use. It has to be put into the mods folder like any other mod.

 Download Fabric API
▼
 CurseForge  Modrinth  GitHub
Develop

Fabric gives you powerful tools to change the game however you like. Use the online template generator to get started creating a mod. You can also use the example mod repository or CLI tools.

Develop a mod
Explore

Extensive documentation is available on the Fabric docs site for both developers and players. Get additional help from the Fabric Discord server, or ask a question on the GitHub Discussion forums.

Visit the docs
Core Toolchain Projects
Fabric Loader A flexible platform-independent mod loader designed for Minecraft and other games and applications.
Yarn Yarn is a set of open Minecraft mappings, free for everyone to use under the Creative Commons Zero license.
Fabric Loom A Gradle plugin enabling developers to easily develop and debug mods.
Fabric Language Kotlin This is a mod that enables usage of the Kotlin programming language for Fabric mods.
Intermediary Intermediary contains match information between different versions of Minecraft, enabling cross version mods.
Tiny Remapper A tiny, efficient tool for remapping JAR files.
Mapping IO A library for reading, manipulating and writing mapping files, with support for a wide range of formats.
Latest Blog Posts
Fabric for Minecraft 26.2

A new version of Minecraft is coming soon with some changes that affect most mod makers. As always, we ask all players to be patient, and give mod developers time to update to this new version. We kindly ask everyone not to pester them. We also recommend all players make backups of their worlds. 26.2 intr...

Continue reading
Fabric for Minecraft 26.1

A new version of Minecraft is coming soon with changes that will affect all mod makers. As always, we ask all players to be patient, and give mod developers time to update to this new version. We kindly ask everyone not to pester them. We also recommend all players make backups of their worlds, especially ...

Continue reading

The contents of this website, unless otherwise indicated, are licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG.

### Develop | Fabric
Fuente: https://fabricmc.net/develop/

Fabric
Download Blog Develop Discuss Docs
Develop

This page provides a curated selection of resources to support both new mod creation and the maintenance of existing projects.

If you require additional help, the Fabric Discord server offers dedicated mod development channels with resources and advice from the community.

Getting Started

If you want to learn how to create mods, you should refer to the official documentation site.

Fabric Documentation
Fabric Wiki (Legacy)
Project Templates

Project templates offer a standardized foundation for Fabric mods - allowing you to quickly create new projects.

Example Mod Repository
Fabric Command Line Tools
Online Template Mod Generator
Javadoc

Easily access Javadoc for toolchain projects and the game, either online or directly within your IDE.

The contents of this website, unless otherwise indicated, are licensed under a Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License.

NOT AN OFFICIAL MINECRAFT PRODUCT. NOT APPROVED BY OR ASSOCIATED WITH MOJANG.

### Developer Guides | Fabric Documentation
Fuente: https://docs.fabricmc.net/develop/

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
Prerequisites
What Does Fabric Offer?
What Does Fabric API Offer?
PAGE AUTHORS
SOURCES & RESOURCES
FabricMC Organization on GitHub
ExampleMod referenced by these docs
University of Helsinki: Java Programming MOOC
Java Platform Group at Oracle: Learn Java
Codecademy: Learn Java
Duke University (via Coursera): Java Programming and Software Engineering Fundamentals
freeCodeCamp (YouTube): Java Programming for Beginners
Modern Java (Online textbook)
Developer Guides 26.2
​

Our community-written developer guides cover many topics, from creating a mod and setting up your environment, all the way to rendering, networking, data generation and more.

Fabric is a lightweight modding toolchain for Minecraft: Java Edition, designed to be simple and easy-to-use. It allows developers to apply modifications ("mods") to the vanilla game, to add new features or change existing mechanics.

This documentation will walk you through modding with Fabric, from creating your first mod and setting up your environment, to advanced topics like rendering, networking, data generation and much more.

Check out the sidebar for a list of the available pages.

TIP

In case you need it at any time, a fully-working mod with all the source code of this documentation is available in the /reference folder on GitHub.

Prerequisites
​

Before you start modding with Fabric, you need to have some understanding of developing with Java, and of Object-Oriented Programming in general.

Here are some resources that might help you familiarize with Java and OOP:

University of Helsinki: Java Programming MOOC
Java Platform Group at Oracle: Learn Java
Codecademy: Learn Java
Duke University (via Coursera): Java Programming and Software Engineering Fundamentals
freeCodeCamp (YouTube): Java Programming for Beginners
Modern Java (Online textbook)
What Does Fabric Offer?
​

The Fabric Project is centered around three main components:

Fabric Loader: a flexible, platform-independent loader of mods, primarily designed for Minecraft: Java Edition
Fabric API: a complementary set of APIs and tools mod developers can use when creating mods
Fabric Loom: a Gradle plugin, enabling developers to easily develop and debug mods
What Does Fabric API Offer?
​

Fabric API provides a wide set of APIs that build on top of the vanilla functionality to allow advanced or simpler development.

For example, it provides new hooks, events, utilities such as transitive access wideners, access to internal registries such as the compostable items registry, and more.

Edit this page on GitHub

L

### Setting up a mod development environment [Fabric Wiki]
Fuente: https://wiki.fabricmc.net/tutorial:setup

skip to content
Fabric Wiki
User Tools
Register
Log In
Site Tools
Search
Recent ChangesSitemap
Trace: • Setting up a mod development environment

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
Creating

## Notas relacionadas
- [[Fabric API sistema de eventos: AttackEntityCallback UseItemCallback UseBlockCallback ServerTickEvents PlayerBlockBreakEvents]]
- [[aplicar un efecto de estado (StatusEffect) al golpear un enemigo en un item custom de Fabric Minecraft]]
- [[registrar un item custom en Fabric Minecraft con Identifier y namespace del mod]]
- [[estructura de un mod Fabric para Minecraft: build.gradle, fabric.mod.json y entrypoint]]
- [[Índice: desarrollo-de-juegos]]
- [[Índice: general]]