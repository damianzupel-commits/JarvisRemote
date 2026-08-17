---
author: jarvis
category: algoritmos
created: '2026-08-02T19:11:37.091787+00:00'
tags:
- investigacion
title: Algoritmo de Dijkstra
updated: '2026-08-02T19:11:37.091787+00:00'
---

Investigación automática de Jarvis sobre "Algoritmo de Dijkstra", basada en 3 página(s) reales visitadas.

## Fuentes

### Algoritmo de Dijkstra - Wikipedia, la enciclopedia libre
Fuente: https://es.wikipedia.org/wiki/Algoritmo_de_Dijkstra

Ir al contenido
Menú principal
Buscar
Donaciones
Crear una cuenta
Acceder
Contenidos ocultar
Inicio
Algoritmo
Complejidad
Pseudocódigo
Otra versión en pseudocódigo sin cola de prioridad
Formulación del algoritmo Dijkstra
Véase también
Referencias
Enlaces externos
Algoritmo de Dijkstra
50 idiomas
Artículo
Discusión
Leer
Editar
Ver historial
Herramientas
Apariencia ocultar
Algoritmo de Dijkstra

Ejecución del algoritmo de Dijkstra
Tipo	Algoritmo de búsqueda
Problema que resuelve	Problema del camino más corto
Estructura de datos	Grafo
Creador	Edsger Dijkstra
Fecha	1959
Clase de complejidad	P
Tiempo de ejecución
Peor caso	
𝑂
(
|
𝐸
|
+
|
𝑉
|
log
⁡
|
𝑉
|
)

[editar datos en Wikidata]


El algoritmo de Dijkstra, también llamado algoritmo de caminos mínimos, es un algoritmo para la determinación del camino más corto, dado un vértice origen, hacia el resto de los vértices en un grafo que tiene pesos en cada arista. Su nombre alude a Edsger Dijkstra, científico de la computación de los Países Bajos que lo concibió en 1956 y lo publicó por primera vez en 1959.[1][2]

La idea subyacente en este algoritmo consiste en ir explorando todos los caminos más cortos que parten del vértice origen y que llevan a todos los demás vértices; cuando se obtiene el camino más corto desde el vértice origen hasta el resto de los vértices que componen el grafo, el algoritmo se detiene. Se trata de una especialización de la búsqueda de costo uniforme y, como tal, no funciona en grafos con aristas de coste negativo (al elegir siempre el nodo con distancia menor, pueden quedar excluidos de la búsqueda nodos que en próximas iteraciones bajarían el costo general del camino al pasar por una arista con costo negativo).[3]

Algoritmoeditar

Teniendo un grafo dirigido ponderado de 
𝑁
 nodos no aislados, sea 
𝑥
 el nodo inicial. Un vector 
𝐷
 de tamaño 
𝑁
 guardará al final del algoritmo las distancias desde 
𝑥
 hasta el resto de los nodos.

Inicializar todas las distancias en 
𝐷
 con un valor infinito relativo, ya que son desconocidas al principio, exceptuando la de 
𝑥
, que se debe colocar en 
0
, debido a que la distancia de 
𝑥
 a 
𝑥
 sería 
0
.
Sea 
𝑎
=
𝑥
 (Se toma 
𝑎
 como nodo actual).
Se recorren todos los nodos adyacentes de a, excepto los nodos marcados. Se les llamará nodos no marcados vi.
Para el nodo actual, se calcula la distancia tentativa desde dicho nodo hasta sus vecinos con la siguiente fórmula: dt(vi) = Da + d(a,vi). Es decir, la distancia tentativa del nodo ‘vi’ es la distancia que actualmente tiene el nodo en el vector D más la distancia desde dicho nodo ‘a’ (el actual) hasta el nodo vi. Si la distancia tentativa es menor que la distancia almacenada en el vector, entonces se actualiza el vector con esta distancia tentativa. Es decir, si dt(vi) < Dvi → Dvi = dt(vi)
Se marca como completo el nodo a.
Se toma como próximo nodo actual el de menor valor en D (puede hacerse almacenando los valores en una cola de prioridad) y se regresa al paso 3, mientras existan nodos no m

### Algoritmo de la ruta más corta de Dijkstra - Introducción gráfica y detallada
Fuente: https://www.freecodecamp.org/espanol/news/algoritmo-de-la-ruta-mas-corta-de-dijkstra-introduccion-grafica/

Menu
Donar

Aprender a codificar — gratis 3,000-horas currículo

OCTOBER 24, 2022
Algoritmo de la ruta más corta de Dijkstra - Introducción gráfica y detallada
Estefania Cassingena Navone

¡Hola! Si siempre has querido aprender cómo funciona el algoritmo de Dijkstra, este artículo es para ti. Entenderás cómo funciona detrás de escenas con una explicación gráfica paso a paso.

Aprenderás:

Conceptos básicos de grafos (una introducción breve).
Aplicaciones del algoritmo de Dijkstra.
Cómo funciona detrás de escenas con un ejemplo paso a paso.

Comencemos. ✨

🔹 Introducción a los grafos

Primero veremos una breve introducción a los grafos.

Conceptos básicos

Los grafos son estructuras de datos usadas para representar "conexiones" entre pares de elementos.

Estos elementos se llaman nodos. Representan objetos reales, personas o entidades.
Las conexiones entre los nodos se llaman aristas o arcos.

Esta es una representación gráfica de un grafo:

Los nodos se representan como círculos de colores y los arcos se representan como líneas que conectan los círculos.

💡 Dato: dos nodos están conectados si existe un arco entre ellos.

Aplicaciones

Los grafos se pueden aplicar directamente a escenarios de la vida real. Por ejemplo, podríamos usar grafos para modelar una red de transporte, en la cual los nodos representarían instalaciones para enviar o recibir productos y los arcos representarían caminos que los conectan (como en el siguiente diagrama).

Red representada como un grafo.
Tipos de grafos

Los grafos pueden ser:

No dirigido: si para cada par de nodos conectados, puedes ir de un nodo al otro en ambas direcciones.
Dirigido: si para cada par de nodos conectados, solo puedes ir de un nodo a otro en una dirección específica. Usamos flechas en lugar de líneas sencillas para representar arcos dirigidos.

💡 Dato: en este artículo, trabajaremos con grafos no dirigidos.

Grafo ponderado

Un grafo ponderado es un grafo cuyos arcos tienen un "peso", "valor", o "costo" asociado. El valor de cada arco puede representar la distancia, tiempo, u otro valor que modele la conexión entre el par de nodos que conecta.

Por ejemplo, en el grafo ponderado que tenemos a continuación, puedes ver un número azul junto a cada arco. Este número representa el valor o costo del arco correspondiente.

💡 Dato: estos valores son muy importantes para el algoritmo de Dijkstra. Verás por qué en tan solo un momento.

🔸 Introducción al algoritmo de Dijkstra

Ahora que ya conoces los concepts básicos de los grafos, comencemos a ver más detalles sobre este algoritmo asombroso.

Aprenderás:

Su propósito y cómo se usa.
Su historia.
Aspectos básicos del algoritmo.
Requisitos.
Propósito y Usos

Con el algoritmo de Dijkstra, puedes encontrar la ruta más corta o el camino más corto entre los nodos de un grafo. Específicamente, puedes encontrar el camino más corto desde un nodo (llamado el nodo de origen) a todos los otros nodos del grafo, generando un árbol del camino más corto.

Este algoritm

### Dijkstra's algorithm - Wikipedia
Fuente: https://en.wikipedia.org/wiki/Dijkstra%27s_algorithm

Jump to content
Main menu
Search
Donate
Create account
Log in
Contents hide
(Top)
History
Algorithm
Description
Pseudocode
Toggle Pseudocode subsection
Using a priority queue
Proof
Toggle Proof subsection
Base case
Induction
Running time
Toggle Running time subsection
Practical optimizations and infinite graphs
Bidirectional Dijkstra
Practical performance considerations
Optimality for comparison-sorting by distance
Specialized variants
Related problems and algorithms
Toggle Related problems and algorithms subsection
Dynamic programming perspective
See also
Notes
References
External links
Dijkstra's algorithm
50 languages
Article
Talk
Read
Edit
View history
Tools
Appearance hide
Text
Small
Standard
Large
Width
Standard
Wide
Color
Automatic
Light
Dark
From Wikipedia, the free encyclopedia
Not to be confused with Dykstra's projection algorithm.
Dijkstra's algorithm
Dijkstra's algorithm to find the shortest path between a and b. It picks the unvisited vertex with the lowest distance, calculates the distance through it to each unvisited neighbor, and updates the neighbor's distance if smaller. Mark visited (set to red) when done with neighbors.

Class	Search algorithm
Greedy algorithm
Dynamic programming[1]
Data structure	Graph
Usually used with priority queue or heap for optimization[2][3]
Worst-case performance	
Θ
(
|
𝐸
|
+
|
𝑉
|
log
⁡
|
𝑉
|
)
[3]

Dijkstra's algorithm (/ˈdaɪk.strəz/, DYKE-strəz) is an algorithm for finding the shortest paths between nodes in a weighted graph, which may represent, for example, a road network. It was conceived by computer scientist Edsger W. Dijkstra in 1956 and published three years later.[4][5][6]

Dijkstra's algorithm finds the shortest path from a given source node to every other node.[7]: 196–206  It can be used to find the shortest path to a specific destination node, by terminating the algorithm after determining the shortest path to that node. For example, if the nodes of the graph represent cities, and the costs of edges represent the distances between pairs of cities connected by a direct road, then Dijkstra's algorithm can be used to find the shortest route between one city and all other cities. A common application of shortest path algorithms is network routing protocols, most notably IS-IS (Intermediate System to Intermediate System) and OSPF (Open Shortest Path First). It is also employed as a subroutine in algorithms such as Johnson's algorithm.

The algorithm uses a min-priority queue data structure for selecting the shortest paths known so far. Before more advanced priority queue structures were discovered, Dijkstra's original algorithm ran in 
Θ
(
|
𝑉
|
2
)
 time, where 
|
𝑉
|
 is the number of nodes.[8][9] Fredman & Tarjan 1984 proposed a Fibonacci heap priority queue to optimize the running time complexity to 
Θ
(
|
𝐸
|
+
|
𝑉
|
log
⁡
|
𝑉
|
)
, where 
|
𝐸
|
 is the number of edges. This is asymptotically the fastest known single-source shortest-path algorithm for arbitrary directed graphs with unbo

## Notas relacionadas
- [[OWASP A07 - Fallas de Identificación y Autenticación]]
- [[Reporte de auditoría -- django -- 2026-07-29]]
- [[Reporte de auditoría -- nest -- 2026-07-29]]
- [[Reporte de auditoría -- luanti -- 2026-07-29]]
- [[Reporte de auditoría -- saas-boilerplate -- 2026-07-29]]
- [[Índice: algoritmos]]