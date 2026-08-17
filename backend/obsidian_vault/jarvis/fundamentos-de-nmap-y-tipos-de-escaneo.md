---
author: jarvis
category: redes
created: '2026-08-02T20:04:17.812592+00:00'
tags:
- investigacion
title: Fundamentos de nmap y tipos de escaneo
updated: '2026-08-02T20:04:17.812592+00:00'
---

Investigación automática de Jarvis sobre "Fundamentos de nmap y tipos de escaneo", basada en 4 página(s) reales visitadas.

## Fuentes

### Elegir las técnicas de escaneo de Nmap: Guía completa | LabEx
Fuente: https://labex.io/es/tutorials/nmap-how-to-choose-nmap-scan-techniques-420322

APRENDER
DESAFÍOS
RESEÑAS
PRECIOS
Iniciar Sesión
Únete Gratis
APRENDER
TUTORIALES
NMAP
Cómo elegir las técnicas de escaneo de Nmap
Nmap
Beginner
Practicar Ahora

CONTENIDO

Introducción
Fundamentos de Escaneo con Nmap
Resumen de Técnicas de Escaneo
Estrategias de Escaneo Eficaces
Resumen
Practicar Ahora
Introducción

En el panorama de la Ciberseguridad en rápida evolución, comprender las técnicas avanzadas de escaneo de redes es crucial para los profesionales que buscan identificar y mitigar posibles vulnerabilidades. Este tutorial proporciona una guía completa sobre la selección e implementación de estrategias de escaneo Nmap efectivas, capacitando a los expertos en seguridad para realizar evaluaciones exhaustivas de la red y mejorar la protección general del sistema.

Fundamentos de Escaneo con Nmap
¿Qué es Nmap?

Nmap (Network Mapper) es una potente herramienta de código abierto utilizada para el descubrimiento de redes y la auditoría de seguridad. Ayuda a los administradores de redes y profesionales de la seguridad a identificar hosts activos, servicios en ejecución y posibles vulnerabilidades dentro de una infraestructura de red.

Conceptos Clave del Escaneo de Redes
Descubrimiento de Redes

El descubrimiento de redes implica mapear los dispositivos y servicios que se ejecutan en una red. Nmap proporciona capacidades completas para:

Detectar hosts activos
Identificar puertos abiertos
Determinar versiones de servicios
Detectar sistemas operativos
Técnicas de Escaneo
graph TD
    A[Técnicas de Escaneo con Nmap] --> B[Escaneo TCP]
    A --> C[Escaneo UDP]
    A --> D[Escaneo SYN]
    A --> E[Escaneo Ping]

Métodos Básicos de Escaneo
Tipo de Escaneo	Descripción	Caso de Uso
TCP Connect	Establecer el handshake completo TCP	Fiable pero ruidoso
SYN Stealth	Escaneo medio abierto	Menos detectable
UDP Scan	Detectar servicios UDP	Identificar servicios no TCP
Instalación de Nmap en Ubuntu

Para instalar Nmap en Ubuntu 22.04, utiliza el siguiente comando:

sudo apt update
sudo apt install nmap

Estructura Básica del Comando Nmap
nmap [tipo de escaneo] [opciones] [objetivo]

Ejemplos de Escaneo Simple
Escanear una sola dirección IP:
nmap 192.168.1.100

Escanear una subred completa:
nmap 192.168.1.0/24

Consideraciones de Seguridad

Al usar Nmap, siempre:

Obtén la autorización adecuada
Respeta las políticas de uso de la red
Usa las técnicas de escaneo de forma responsable
Enfoque de Aprendizaje de LabEx

En LabEx, recomendamos la práctica práctica para dominar las técnicas de escaneo con Nmap. Nuestras rutas de aprendizaje de ciberseguridad proporcionan experiencias prácticas y guiadas para comprender los fundamentos del escaneo de redes.

Resumen de Técnicas de Escaneo
Entendiendo los Tipos de Escaneo con Nmap
1. Técnicas de Escaneo TCP
Escaneo TCP Connect
nmap -sT 192.168.1.0/24

Escaneo TCP SYN Stealth
sudo nmap -sS 192.168.1.0/24

graph TD
    A[Tipos de Escaneo TCP] --> B[Escaneo Connect]
    A --> C[Escaneo SYN Stealth]
    A --> D[Escaneo ACK]

2. 

### Aprende los Fundamentos de Nmap y las Técnicas de Escaneo | LabEx
Fuente: https://labex.io/es/tutorials/nmap-learn-nmap-fundamentals-and-scanning-techniques-415937

APRENDER
DESAFÍOS
RESEÑAS
PRECIOS
Iniciar Sesión
Únete Gratis
APRENDER
TUTORIALES
NMAP
Aprende los Fundamentos de Nmap y las Técnicas de Escaneo
Nmap
Beginner
Practicar Ahora

CONTENIDO

Introducción
Comprender los conceptos básicos de Nmap
Explorando técnicas de escaneo de puertos con Nmap
Comprender las plantillas de temporización y rendimiento
Formatos de salida y análisis de resultados de escaneo
Resumen
Practicar Ahora
Introducción

En este laboratorio, aprenderás los fundamentos de Nmap, una poderosa herramienta de escaneo de redes comúnmente utilizada en ciberseguridad para la descubrimiento de redes y auditoría de seguridad. Explorarás cómo utilizar Nmap para escanear redes, descubrir puertos abiertos e identificar servicios en ejecución.

Al dominar estas técnicas, adquirirás habilidades esenciales para la administración de redes y la evaluación de seguridad. Esta experiencia práctica ofrecerá conocimientos prácticos aplicables en escenarios del mundo real, ayudándote a comprender la infraestructura de red y las consideraciones de seguridad.

Comprender los conceptos básicos de Nmap

Nmap, abreviatura de Network Mapper, es una herramienta de código abierto que desempeña un papel crucial en el descubrimiento de redes y la auditoría de seguridad. En el mundo de la ciberseguridad, es como un detective que utiliza paquetes IP sin procesar para recopilar información. Con Nmap, puedes averiguar qué hosts están presentes en una red, qué servicios están proporcionando esos hosts, el sistema operativo que están ejecutando y otras características importantes.

Comencemos nuestro viaje con los conceptos básicos de Nmap. Primero, necesitamos abrir una terminal. La terminal es como un centro de comandos donde puedes escribir comandos para interactuar con tu sistema. Puedes abrirla haciendo clic en el icono de la terminal en la barra de tareas o presionando Ctrl+Alt+T.

Una vez abierta la terminal, debemos asegurarnos de estar en el directorio del proyecto. El directorio del proyecto es una carpeta específica donde se llevarán a cabo todos nuestros archivos relacionados y operaciones para este experimento. Para navegar al directorio del proyecto, utiliza el siguiente comando:

cd /home/labex/project


Ahora que estamos en el lugar correcto, veamos la versión de Nmap instalada en nuestro sistema. Saber la versión es importante porque diferentes versiones pueden tener diferentes características y comportamientos. Para verificar la versión, ejecuta este comando:

nmap --version


Después de ejecutar el comando, deberías ver una salida similar a esta. Esta salida muestra la versión de Nmap instalada en tu sistema, junto con alguna otra información sobre las bibliotecas con las que se compiló y los motores nsock disponibles.

Nmap version 7.80 ( https://nmap.org )
Platform: x86_64-pc-linux-gnu
Compiled with: liblua-5.3.3 openssl-1.1.1f libpcre-8.39 libpcap-1.9.1 nmap-libdnet-1.12 ipv6
Compiled without:
Available nsock engines: epoll poll select


Ahora, re

### Guía Completa de Nmap - Escaneo y Análisis de Redes
Fuente: https://www.alfonsora6.com/blog/posts/nmap/

Inicio
Experiencia
Proyectos
Sobre mí
Blog
Nmap
17 de febrero de 2026
Guía Completa de Nmap - Escaneo y Análisis de Redes

Nmap (Network Mapper) es una herramienta de código abierto para exploración de redes y auditorías de seguridad. Creada por Gordon Lyon (también conocido como Fyodor), se ha convertido en el estándar de facto para el descubrimiento de hosts, escaneo de puertos, detección de servicios y sistemas operativos en redes.

En esta guía se explicarán los conceptos fundamentales de Nmap y se proporcionarán ejemplos prácticos de uso, desde escaneos básicos hasta técnicas avanzadas de evasión y análisis mediante scripts NSE.

Instalación de Nmap

A continuación se describen los pasos para instalar Nmap en diferentes sistemas operativos:

Linux (Debian/Ubuntu)
sudo apt update
sudo apt install nmap
Linux (Red Hat/CentOS/Fedora)
sudo yum install nmap
# o en versiones más recientes
sudo dnf install nmap
macOS
# Usando Homebrew
brew install nmap

# Usando MacPorts
sudo port install nmap
Windows

Descarga el instalador desde la página oficial de Nmap y ejecuta el asistente de instalación.

Verificar instalación
nmap --version
Conceptos Básicos

La sintaxis general de Nmap sigue la siguiente estructura:

Sintaxis General
nmap [Tipo de Escaneo] [Opciones] {objetivo(s)}
Especificar Objetivos
# IP individual
nmap 192.168.1.1

# Múltiples IPs
nmap 192.168.1.1 192.168.1.5 192.168.1.10

# Rango de IPs
nmap 192.168.1.1-20
nmap 192.168.1.0/24

# Subred completa
nmap 192.168.1.0/24
nmap 192.168.0.0/16

# Hostname
nmap scanme.nmap.org
nmap example.com

# Múltiples hosts
nmap 192.168.1.1 scanme.nmap.org

# Lista de hosts desde archivo
nmap -iL targets.txt

# Rango excluyendo IPs
nmap 192.168.1.0/24 --exclude 192.168.1.1
nmap 192.168.1.0/24 --exclude 192.168.1.1,192.168.1.5

# Excluir desde archivo
nmap 192.168.1.0/24 --excludefile exclude.txt
Tipos de Escaneo de Puertos

Nmap ofrece diferentes tipos de escaneo, cada uno con características específicas que los hacen más adecuados para distintos escenarios:

Escaneo TCP Connect (-sT)

Completa el three-way handshake TCP. Es el escaneo por defecto cuando no tienes privilegios de root.

nmap -sT 192.168.1.1
nmap -sT 192.168.1.0/24

Ventajas:

No requiere privilegios especiales
Más confiable en redes con firewalls mal configurados

Desventajas:

Más fácil de detectar
Más lento que otros métodos
Escaneo SYN (-sS)

También conocido como “half-open scanning” o “stealth scan”. Es el escaneo por defecto con privilegios de root.

sudo nmap -sS 192.168.1.1
sudo nmap -sS 192.168.1.0/24

Ventajas:

Más rápido que TCP Connect
Menos detectable
Funciona contra la mayoría de firewalls

Desventajas:

Requiere privilegios de root/administrator
Escaneo UDP (-sU)

Escanea puertos UDP, útil para servicios como DNS, DHCP, SNMP.

sudo nmap -sU 192.168.1.1
sudo nmap -sU -p 53,67,161 192.168.1.1

# Combinado con TCP SYN
sudo nmap -sU -sS 192.168.1.1

Nota: Los escaneos UDP son significativamente más lentos que los TCP debido a la n

### Medium
Fuente: https://medium.com/@claudio.drewsc/nmap-de-0-a-experto-anatom%C3%ADa-de-un-escaneo-profesional-desde-la-terminal-8e9a81a18271

Get app
Write

Sign up

Sign in

## Notas relacionadas
- [[Credenciales por defecto en dispositivos IoT y como se explotan]]
- [[Ciberseguridad: Índice y Mapa de Contenidos]]
- [[TLS SSL buenas practicas y errores comunes de configuracion]]
- [[Prevencion de SQL injection en distintos lenguajes]]
- [[Algoritmo de Dijkstra]]
- [[Índice: redes]]