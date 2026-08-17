---
author: jarvis
category: codigo-seguro
created: '2026-08-02T20:03:06.364042+00:00'
tags:
- investigacion
title: Gestion segura de contrasenas hashing bcrypt argon2 salting
updated: '2026-08-02T20:03:06.364042+00:00'
---

Investigación automática de Jarvis sobre "Gestion segura de contrasenas hashing bcrypt argon2 salting", basada en 4 página(s) reales visitadas.

## Fuentes

### Hashing de contraseñas: bcrypt vs. Argon2 vs. PBKDF2
Fuente: https://www.encryptionconsulting.com/es/Almacenamiento-de-contrase%C3%B1as-bien-hecho%3A-hash--salting-y-bcrypt-vs-argon2-vs-pbkdf2/

Ir al contenido

Próximamente estarán disponibles los certificados de 47 días. ¿Todo listo?

Actúa ahora →
Iniciar sesión

Español

Buscar
Productos
 
Soluciones
 
Servicios
 
Capacitaciones
 
Recursos
 
Empresa
Solicitar una demo
Contáctenos
Blog
Criptografía
Almacenamiento de contraseñas correcto: Hashing, Salting y bcrypt frente a Argon2 frente a PBKDF2
Publicado por
Shubham Chamola
24 de junio de 2026
10 minutos

La mayoría de las personas nunca piensan en cómo se almacenan sus contraseñas después de registrarse. Simplemente confían en que las empresas lo gestionan correctamente. Pero esa confianza no siempre está justificada. El almacenamiento de contraseñas es uno de los aspectos más problemáticos en la seguridad de las aplicaciones, y las consecuencias de un mal manejo son graves.

Cada año, las filtraciones exponen millones de credenciales de usuario. En muchos casos, esas credenciales se almacenaban de forma que resultaba fácil de descifrar. Sin salting, débil hashA veces, incluso en texto plano. No se trata de casos excepcionales, sino de fallos recurrentes que afectan a usuarios reales.

Esta publicación explica cómo funciona el almacenamiento seguro de contraseñas, desde los conceptos básicos de hash y salting hasta una comparación práctica de bcrypt, Argon2 y PBKDF2. Si estás diseñando o revisando un sistema de autenticación, este es el punto de partida.

Por qué es importante el almacenamiento seguro de contraseñas

Cuando los atacantes roban una base de datos de contraseñas, no obtienen instantáneamente todas las contraseñas. Lo que obtienen es un conjunto de representaciones almacenadas. Si estas se crearon correctamente, los datos les resultan prácticamente inútiles. De lo contrario, pueden recuperar miles de contraseñas reales en cuestión de horas.

El riesgo no se limita a una sola cuenta. Las personas reutilizan contraseñas en distintos servicios. Una contraseña descifrada en una aplicación de bajo riesgo puede desbloquear cuentas de correo electrónico, accesos bancarios o sistemas corporativos. Esta reacción en cadena explica por qué incluso las aplicaciones pequeñas son responsables de la seguridad general de sus usuarios.

También existe una dimensión de cumplimiento. Marcos como NIST SP 800-63B, GDPR, y PCI-DSS Todos tienen expectativas sobre cómo se protegen los datos de autenticación. Un almacenamiento deficiente de contraseñas es tanto un fallo técnico como normativo, con las consiguientes sanciones y daños a la reputación.

Comprender el hashing y el salting de contraseñas

Una función hash criptográfica toma una contraseña como entrada y produce una salida de longitud fija llamada hash o resumen. La característica clave es que este proceso solo funciona en una dirección. No se puede revertir un hash para recuperar la contraseña original. Por lo tanto, en lugar de almacenar las contraseñas directamente, los sistemas almacenan sus hashes. Al iniciar sesión, la contraseña ingresada se somete a un proceso de hash y se com

### ¿Cómo guardar contraseñas? Hashing + salt bien hecho (bcrypt/Argon2) | ITD
Fuente: https://itdef.net/es/learn/password-storage-hashing-salt

Saltar al contenido
>_
ITD
ITD
Plataforma de seguridad web
Boletín de amenazas
Incidentes y vulnerabilidades
Historia
Glosario
Guías de seguridad
Por framework
Herramientas gratuitas
ES
ITD
Guías de seguridad
Cómo guardar contraseñas con seguridad — la forma correcta de aplicar hash y salt

GUÍAS DE SEGURIDAD

#contraseñas
#hashing
#autenticación
Cómo guardar contraseñas con seguridad — la forma correcta de aplicar hash y salt

Cómo guardar contraseñas con seguridad: por qué fallan el texto plano, el cifrado y los hashes simples, qué aporta un salt por usuario y por qué la respuesta es un hash lento (Argon2/bcrypt/scrypt). Cómo elegirlo, ajustarlo y migrar un sistema.

Publicado 2026-06-27
Actualizado 2026-06-27
6 min de lectura

"¿Cómo debería guardar exactamente las contraseñas de los usuarios en la base de datos?" — todo desarrollador se topa con esta pregunta una vez. La respuesta es clara. Aquí va la forma segura de guardarlas, por orden, sin pasos de ataque.

LA RESPUESTA PRIMERO

Hay exactamente una respuesta correcta para guardar contraseñas: un salt por usuario más un hash lento y diseñado a propósito. En concreto, haz de Argon2id tu primera opción (con bcrypt / scrypt como alternativas). El texto plano está mal, el cifrado está mal, y el MD5/SHA-256 simple está mal. La regla más importante: no lo construyas tú — usa la función de contraseñas estándar de tu lenguaje/framework. Después, solo revisa el coste de vez en cuando.

Por qué el texto plano, el cifrado y los hashes simples fallan todos

Asume que la base de datos se filtrará algún día. Cuando ocurra, el daño difiere enormemente según el método de almacenamiento.

Texto plano: toda contraseña queda expuesta en el instante en que se filtra. Peor aún, la reutilización de contraseñas encadena la brecha hacia los otros servicios del usuario. El peor caso.
Cifrado (reversible): la clave lo revierte — así que si la clave se filtra junto con ello, vuelves al texto plano. Una contraseña nunca necesita leerse de vuelta, así que ser reversible no te aporta nada.
Hash simple (MD5/SHA-256): un hash rápido permite a un atacante probar conjeturas a gran velocidad. Las contraseñas comunes caen ante las tablas rainbow y la fuerza bruta.
Las "cuatro etapas" hacia lo seguro

Lo más rápido es entenderlo como ir añadiendo una corrección a la vez a un método débil.

1. texto plano: se acabó si se filtra
↓ hazlo de un solo sentido
2. hash simple: débil ante las tablas rainbow
↓ añade un salt por usuario
3. hash con salt: tablas derrotadas, pero la fuerza bruta sigue siendo rápida
↓ hazlo deliberadamente lento
4. hash con salt + lento (Argon2id / bcrypt): esta es la respuesta
texto plano → hash simple → con salt → hash lento. Solo al final es realmente 'almacenamiento seguro'.

La idea clave: un salt y un hash lento hacen trabajos distintos. Un salt derrota la precomputación (tablas rainbow) y el descifrado masivo por reutilización. Un hash lento reduce la fuerza bruta a un ritmo impracticable. Necesitas

### bcrypt vs Argon2: elegir parámetros de hashing de contraseñas | AppMaster
Fuente: https://appmaster.io/es/blog/bcrypt-vs-argon2-elegir-parametros-hash-contrasenas

🚀 Lanza RÁPIDO: utiliza a los ingenieros de AppMaster ProServices
Producto
Constructor de apps móviles
Arrastra y suelta para apps móviles perfectas
Integraciones
Integra todas tus herramientas favoritas
Diseñador de apps web
Crea panel de admin o portal de clientes
Diseñador de modelos de datos
Modelos de datos con cualquier tipo de campo
Editor de procesos de negocio
Crea procesos de negocio visualmente
Industrias
Elige tu solución de industria
No-Code
Por qué elegir una plataforma no-code
Precios
Recursos
Blog
Noticias sobre desarrollo no-code
Universidad AppMaster
Comienza con AppMaster
Historias de éxito
Lee las historias de nuestros clientes
Documentación
Construye en nuestra plataforma
Comunidad
Encuentra la solución a tus problemas
AppMaster 101
Curso intensivo

¿No sabes por dónde empezar? Comienza con nuestro curso intensivo para principiantes y crea tu primer proyecto.

Iniciar curso
Empresa
Carreras
¡Estamos contratando! ¡Únete a nosotros!
Programa de socios
Obtén todos los beneficios de AppMaster
Contrata un experto
Construye con un profesional no-code
Servicios profesionales
Construye tu aplicación con nosotros
Contacto
Ponte en contacto con nosotros
Síguenos:
Community
Facebook
Twitter
LinkedIn
YouTube
Instagram
English
Русский
Français
Español
Deutsch
日本語
한국어
हिन्दी
বাংলা
中文
العربية
Português
Bahasa Indonesia
Türkçe
Italiano
Polski
Tiếng Việt
Nederlands
ไทย
Contactar
Prueba gratis
Inicio
Blog
bcrypt vs Argon2: elegir parámetros de hashing de contraseñas
04 ene 2026
·
6 min de lectura
bcrypt vs Argon2: elegir parámetros de hashing de contraseñas

bcrypt vs Argon2 explicado: compara rasgos de seguridad, costes de rendimiento en escenarios reales y cómo elegir parámetros seguros para backends web modernos.

Qué problema resuelve el hash de contraseñas

El hashing de contraseñas permite que un backend guarde una contraseña sin almacenar la contraseña en sí. Cuando alguien se registra, el servidor pasa la contraseña por una función unidireccional y guarda el resultado (el hash). Al iniciar sesión, se hashea la contraseña que escribió el usuario y se compara con lo almacenado.

Un hash no es cifrado. No hay forma de revertirlo. Esa propiedad unidireccional es exactamente por lo que se usa el hashing para contraseñas.

Entonces, ¿por qué no usar un hash rápido normal como SHA-256? Porque rápido es lo que quieren los atacantes. Si se filtra una base de datos, los atacantes no prueban contraseñas intentando ingresar una por una en el sitio. Adivinan offline usando la lista de hashes robada, empujando intentos al ritmo que les permita su hardware. Con GPUs, los hashes rápidos se pueden probar a enorme escala. Incluso con salts únicos, un hash rápido sigue siendo barato de forzar por fuerza bruta.

Aquí está el modo de falla realista: una pequeña aplicación web pierde su tabla de usuarios en una brecha. El atacante obtiene correos y hashes de contraseñas. Si esos hashes se generaron con una función rápida, las contraseñas comunes y pequeñas 

### Password Hashing: bcrypt vs. Argon2 vs. PBKDF2
Fuente: https://www.encryptionconsulting.com/password-storage-done-right-hashing-salting-and-bcrypt-vs-argon2-vs-pbkdf2/

Skip to content

47-Day Certificates Are Coming. Are You Ready?

Act Now →
Login

English

Search
Products
 
Solutions
 
Services
 
Trainings
 
Resources
 
Company
Request a Demo
Contact Us
Blogs
Cryptography
Password Storage Done Right: Hashing, Salting, and bcrypt vs. Argon2 vs. PBKDF2
Posted by
Shubham Chamola
June 24, 2026
10 minutes

Most people never think about how their passwords are stored after clicking Sign Up. They just trust that companies are handling it the right way. But that trust is not always earned. Password storage is one of the most commonly mishandled areas in application security, and the consequences of getting it wrong are serious.

Every year, breaches expose millions of user credentials. In many cases, those credentials were stored in ways that made cracking them easy. No salting, weak hashes, sometimes even plaintext. These are not edge cases. They are recurring failures that affect real users.

This post explains what secure password storage actually looks like, from the basics of hashing and salting to a practical comparison of bcrypt, Argon2, and PBKDF2. If you are building or reviewing an authentication system, this is where to start.

Why Secure Password Storage Matters

When attackers steal a password database, they do not instantly have everyone’s passwords. What they have is a set of stored representations. If those were created properly, the data is largely useless to them. If not, they can recover thousands of real passwords in a matter of hours.

The risk does not stop at one account. People reuse passwords across services. A cracked password from a low-stakes app can unlock email accounts, banking logins, or corporate systems. That chain reaction is why even small applications carry responsibility for their users’ broader security.

There is also a compliance dimension. Frameworks like NIST SP 800-63B, GDPR, and PCI-DSS all carry expectations around how authentication data is protected. Poor password storage is both a technical failure and a regulatory one, with penalties and reputational damage to follow.

Understanding Hashing and Password Salting

A cryptographic hash function takes a password as input and produces a fixed-length output called a hash or digest. The key property is that this process only goes one way. You cannot reverse a hash to get the original password back. So instead of storing passwords directly, systems store their hashes. At login, the entered password is hashed and compared to what was stored.

This sounds secure enough. But general purpose hash functions like MD5 and SHA-256 were built for speed, not for passwords. A modern GPU can compute billions of SHA-256 hashes per second. That speed is an advantage for attackers running brute-force or dictionary attacks.

Password salting addresses a specific attack: rainbow tables. A rainbow table is a precomputed lookup of hashes for common passwords. An attacker can take a stolen hash and look it up in seconds without doing any real co

## Notas relacionadas
- [[Criptografía Aplicada: Qué NO Hacer]]
- [[OWASP A02 - Fallas Criptográficas]]
- [[Prevencion de SQL injection en distintos lenguajes]]
- [[JWT JSON Web Tokens vulnerabilidades comunes y buenas practicas]]
- [[Reporte de auditoría -- SuperSaaSFastAPI -- 2026-07-29]]
- [[Índice: codigo-seguro]]