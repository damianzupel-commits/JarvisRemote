---
author: jarvis
created: '2026-07-28T00:00:00.000000+00:00'
tags:
- seguridad
- owasp
- vulnerabilidad
title: OWASP A01 - Control de Acceso Roto
updated: '2026-07-28T00:00:00.000000+00:00'
---

Categoría #1 del [[OWASP Top 10 - Resumen]] 2021 (subió desde el puesto #5 en 2017 — es la más prevalente hoy). Ocurre cuando un usuario puede actuar fuera de los permisos que debería tener.

## Patrones concretos a buscar en código
- **IDOR (Insecure Direct Object Reference):** el endpoint usa un ID que viene del cliente para buscar un recurso, sin validar que ese recurso pertenezca al usuario autenticado.
  ```python
  # vulnerable: cualquier usuario logueado puede leer la factura de cualquier otro
  @app.get("/invoices/{invoice_id}")
  def get_invoice(invoice_id: int, user: User = Depends(current_user)):
      return db.query(Invoice).get(invoice_id)

  # seguro: se filtra por owner
  def get_invoice(invoice_id: int, user: User = Depends(current_user)):
      inv = db.query(Invoice).filter_by(id=invoice_id, owner_id=user.id).first()
      if not inv:
          raise HTTPException(404)
      return inv
  ```
- **Falta de chequeo de rol en rutas admin:** la ruta existe y funciona, pero solo confía en que el frontend no muestre el botón (control de acceso "por oscuridad" en el cliente, no en el servidor).
- **CORS mal configurado:** `Access-Control-Allow-Origin: *` combinado con `Access-Control-Allow-Credentials: true` (inválido por spec pero a veces se ve, y aun sin credentials abre superficie).
- **Elevación de privilegio por parámetro:** un campo `role` o `is_admin` que viene en el body de un request de actualización de perfil y se aplica sin filtrar (mass assignment).
- **Path traversal como forma de acceso roto** — ver nota dedicada [[Path Traversal]].

## Qué buscan las reglas de Semgrep/CodeQL para esto
Reglas que detectan: endpoints sin decorador de auth, queries a DB por ID sin cláusula de ownership al lado, deserialización de JSON directo a un modelo ORM sin whitelist de campos (mass assignment). Ver [[Semgrep en la Práctica]] y [[CodeQL en la Práctica]] — este tipo de bug es más de *lógica de negocio* que de sintaxis, así que el SAST clásico basado en patrones detecta poco de esto (más falsos negativos que en A03); CodeQL con su análisis de flujo de datos hace mejor trabajo que Semgrep en reglas puramente sintácticas.

## Mitigación
Autorización centralizada (middleware/decorador, no repetida a mano en cada endpoint), deny-by-default, y siempre filtrar por ownership en la query, no verificar *después* de traer el objeto. Ver [[Autenticación y Autorización]].
