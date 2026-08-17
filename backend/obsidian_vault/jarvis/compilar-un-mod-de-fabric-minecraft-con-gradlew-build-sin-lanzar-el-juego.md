---
author: jarvis
category: desarrollo-de-juegos
created: '2026-08-10T16:47:21.673420+00:00'
tags:
- investigacion
title: compilar un mod de Fabric Minecraft con gradlew build sin lanzar el juego
updated: '2026-08-10T16:47:21.673420+00:00'
---

Investigación automática de Jarvis sobre "compilar un mod de Fabric Minecraft con gradlew build sin lanzar el juego", basada en 3 página(s) reales visitadas.

## Fuentes

### Reddit - Prove your humanity
Fuente: https://www.reddit.com/r/fabricmc/comments/slfgkg/how_do_i_compile_my_mod/

Prove your humanity

We’re committed to safety and security. But not for bots. Complete the challenge below and let us know you’re a real person.

Reddit, Inc. © "2026". All rights reserved.
User Agreement
Privacy Policy
Content Policy
Help

### Building a Mod | Fabric Documentation
Fuente: https://docs.fabricmc.net/develop/getting-started/building-a-mod

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
Choose Your IDE
Building in the Terminal
Installing and Sharing
PAGE AUTHORS
Building a Mod 26.2
​

Learn how to build a Minecraft mod that can be shared or tested in a production environment.

Once your mod is ready for testing, you're able to export it into a JAR file which can be shared on mod hosting websites, or used to test your mod in production alongside other mods.

Choose Your IDE
​
IntelliJ IDEA
Visual Studio Code
Building in the Terminal
​

WARNING

Using the terminal to build a mod rather than an IDE may cause issues if your default Java installation does not match what the project is expecting. For more reliable builds, consider using an IDE that allows you to easily specify the correct version of Java.

Open a terminal from the same directory as the mod project directory, and run the following command:

Windows
macOS/Linux
powershell
./gradlew.bat build

The JARs should appear in the build/libs folder in your project. Use the JAR file with the shortest name outside development.

Installing and Sharing
​

From there, the mod can be installed as normal, or uploaded to trustworthy mod hosting sites like CurseForge and Modrinth.

Edit this page on GitHub

Last updated: 27/2/26, 16:02

Pager
Previous page
Generating Sources
Next page
IDE Tips and Tricks

### Instalando todo el entorno de trabajo [Fabric Wiki]
Fuente: https://wiki.fabricmc.net/es:tutorial:setup

skip to content
Fabric Wiki
User Tools
Register
Log In
Site Tools
Search
Recent ChangesSitemap
Trace: • Instalando todo el entorno de trabajo
es:tutorial:setup
Table of Contents
Instalando todo el entorno de trabajo
Prerrequisitos
Instalando el mod
Manualmente
Generating Minecraft Sources
Getting started
Advice
Troubleshooting
"no usages" on every method
Missing sounds
Could not find or load class net.fabricmc.devlaunchinjector.Main: java.lang.ClassNotFoundException / "no JDK module specified" in the run config
java.lang.ClassNotFoundException: net.fabricmc.loader.impl.launch.knot.KnotClient / java.lang.TypeNotPresentException: Type net/minecraft/util/Identifier not present / java.lang.RuntimeException: Minecraft game provider couldn't locate the game! The game may be absent from the class path, lacks some expected files, suffers from jar corruption or is of an unsupported variety/version.
What's Next?
Instalando todo el entorno de trabajo
Prerrequisitos
Un “Kit de desarrollo en Java (JDK)” para Java 17 (recomendado) o una versión posterior. Visita https://adoptium.net/releases.html para ver los instaladores.
Si eres un profesional, puedes descargarlo de http://jdk.java.net/, que necesita ser extraído y ajustar las variables en el sistema manualmente.
Cualquier IDE que permita usar Java, por ejemplo Intellij IDEA(El más usado y recomendado) y Eclipse. También puedes usar otros editores de código, como Visual Studio Code.
Si no has usado nada de esto antes, te recomendamos usar Intellij IDEA, ya que es el que más la gente escoge para modding.
Instalando el mod
Manualmente
Copia los archivos para empezar en fabric-example-mod (o desde the template generator, si deseas usar Kotlin u otras funciones.) puedes eliminar los archivos LICENSE y el README.md - ya que no son necesarias para tu mod, luego podrás hacerlas como prefieras.
Edita el archivo gradle.properties:
Asegúrate de poner archives_base_name y maven_group a tu preferencia.
Asegúrate de actualizar las versiones del Minecraft, los mapeos, el loader y el loom - todo esto puedes saberlo con más detalle en

https://fabricmc.net/develop/ - para poder ajustar las versiones como tú desees.

Agrega cualquier otra dependencia que planeas usar al build.gradle.
Importa el build.gradle a tu IDLE. Puedes ver más detalle en los siguientes pasos dependiendo tu IDLE.
¡Disfruta el modding!
Cambiar el Fabric Mod ID

Desde Minecraft 1.19.2, el mod ID de la Fabric API cambio de fabric a fabric-api. Cuando estés haciendo un backport de 1.19.2 a versiones más nuevas, asegúrate de cambiar esta parte en la sección de depends en tu fabric.mod.json.

IntelliJ IDEA

Si estas usando IntelliJ IDEA, por favor sigue los siguientes pasos:

En el menú principal del IDLE, selecciona 'Import Project' (o File → Open… si ya tienes un proyecto abierto).
Select the project's build.gradle file to import the project.
After Gradle is done setting up, close (File → Close Project) and re-open the project to fix run configurations not 

## Notas relacionadas
- [[aplicar un efecto de estado (StatusEffect) al golpear un enemigo en un item custom de Fabric Minecraft]]
- [[Herramientas SAST y SCA - Resumen]]
- [[Índice: desarrollo-de-juegos]]
- [[registrar un item custom en Fabric Minecraft con Identifier y namespace del mod]]
- [[estructura de un mod Fabric para Minecraft: build.gradle, fabric.mod.json y entrypoint]]