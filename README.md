# Catálogo Envaperu – API REST

Esta aplicación Flask expone un conjunto de endpoints para gestionar clientes, productos y catálogos de negociación.  
Todas las rutas están bajo el prefijo `/api`.

> Los ejemplos usan `curl` y se expresan en **JSON**; ajusta `{{base}}` (URL base) y `{{token}}` (token JWT) según tu entorno.

---
## 1. Autenticación

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/register` | Crea el **primer** usuario (solo permitido si la tabla está vacía). |
| POST | `/api/auth/login` | Devuelve *access_token* JWT y *refresh_token* opaco. |
| POST | `/api/auth/refresh` | Rota el refresh y emite nuevo *access* + *refresh*. |
| POST | `/api/auth/logout` | Revoca un refresh_token específico. |
| GET  | `/api/auth/whoami` | Devuelve el payload del JWT (requiere `Authorization`). |

### 1.1 Registrar primer usuario
```bash
curl -X POST {{base}}/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@empresa.com","password":"Secret123","nombre":"Admin"}'
# 201 Created
```

### 1.2 Login
```bash
curl -X POST {{base}}/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@empresa.com","password":"Secret123"}'
# 200 OK
# {
#   "access_token":"eyJ...",
#   "refresh_token":"4b8e...",
#   "user": {"id":1,"email":"admin@empresa.com","nombre":"Admin","roles":[]}
# }
```

Guarda `access_token` en `{{token}}` y úsalo en el header:
```bash
-H "Authorization: Bearer {{token}}"
```

### 1.3 Refresh (rotación)
```bash
curl -X POST {{base}}/api/auth/refresh \
     -H "Content-Type: application/json" \
     -d '{"refresh_token":"4b8e..."}'
# 200 -> nuevo access y refresh
```

### 1.4 Logout
```bash
curl -X POST {{base}}/api/auth/logout \
     -H "Content-Type: application/json" \
     -d '{"refresh_token":"4b8e..."}'
# 200 {"ok":true}
```

### 1.5 Whoami (test del token)
```bash
curl -X GET {{base}}/api/auth/whoami \
     -H "Authorization: Bearer {{token}}"
# 200 {"sub":1,"email":"admin@empresa.com","roles":[]}
```

---
## 2. Productos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/productos` | Lista productos (`search`, `familia`, `page`, `per_page`). |
| POST | `/api/productos` | Crea un producto. |
| GET | `/api/productos/{id}` | Obtiene un producto por id. |
| PATCH | `/api/productos/{id}` | Actualiza campos del producto. |
| DELETE | `/api/productos/{id}` | Elimina producto (si no está referenciado). |
| PATCH | `/api/productos/{id}/imagen` | Genera o actualiza `imagen_key`. |
| POST | `/api/productos/{id}/imagen/upload` | Sube la imagen real (multipart/form-data). |
| GET | `/api/productos/{id}/imagen/url` | Devuelve URL firmada (`expires_in`). |

### 2.1 Listar productos
```bash
curl -X GET "{{base}}/api/productos?search=lapicero&familia=Útiles&page=1&per_page=10" \
     -H "Authorization: Bearer {{token}}"
```

### 2.2 Crear producto
```bash
curl -X POST {{base}}/api/productos \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{
       "nombre":"Lapicero azul",
       "um":"UNID",              # DOC | UNID | CIENTO
       "doc_x_bulto_caja":144,
       "doc_x_paq":12,
       "precio_exw":1.25,
       "familia":"Útiles"
     }'
```

### 2.3 Obtener producto
```bash
curl -X GET {{base}}/api/productos/1 \
     -H "Authorization: Bearer {{token}}"
```

### 2.4 Editar producto (PATCH)
```bash
curl -X PATCH {{base}}/api/productos/1 \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{"precio_exw":1.10,"familia":"Oficina"}'
```

### 2.5 Eliminar producto
```bash
curl -X DELETE {{base}}/api/productos/1 \
     -H "Authorization: Bearer {{token}}"
```

### 2.6 Gestionar imágenes

1) **Generar `imagen_key`**  
```bash
curl -X PATCH {{base}}/api/productos/1/imagen \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{"filename":"foto.png"}'
# -> {"ok":true,"imagen_key":"productos/000001/lapicero-xxxx.png"}
```

2) **Subir archivo**  
```bash
curl -X POST {{base}}/api/productos/1/imagen/upload \
     -H "Authorization: Bearer {{token}}" \
     -F "file=@./foto.png"
```

3) **Obtener URL firmada**  
```bash
curl -X GET "{{base}}/api/productos/1/imagen/url?expires_in=3600" \
     -H "Authorization: Bearer {{token}}"
# -> {"url":"https://...","expires_in":3600}
```

---
## 3. Clientes

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/clientes` | Lista clientes (`search`, `pais`, `ciudad`, `page`, `per_page`). |
| POST | `/api/clientes` | Crea un cliente. |
| GET | `/api/clientes/{id}` | Obtiene un cliente por id. |
| PATCH | `/api/clientes/{id}` | Actualiza datos del cliente. |
| DELETE | `/api/clientes/{id}` | Elimina cliente (si no está referenciado). |

### 3.1 Listar clientes
```bash
curl -X GET "{{base}}/api/clientes?search=limeña&pais=PE&page=1&per_page=20" \
     -H "Authorization: Bearer {{token}}"
```

### 3.2 Crear cliente
```bash
curl -X POST {{base}}/api/clientes \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{
       "tipo_doc":"RUC",          # DNI | RUC | CE | PASAPORTE | OTRO
       "num_doc":"20123456789",
       "nombre":"Cliente S.A.",
       "pais":"PE",
       "ciudad":"Lima"
     }'
```

### 3.3 Obtener cliente
```bash
curl -X GET {{base}}/api/clientes/1 \
     -H "Authorization: Bearer {{token}}"
```

### 3.4 Editar cliente
```bash
curl -X PATCH {{base}}/api/clientes/1 \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{"ciudad":"Arequipa","clasificacion_riesgo":"BAJO"}'
```

### 3.5 Eliminar cliente
```bash
curl -X DELETE {{base}}/api/clientes/1 \
     -H "Authorization: Bearer {{token}}"
```

---
## 4. Catálogos

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/catalogos` | Lista catálogos (`cliente_id`, `producto_id`, `estado`, `with_final`, `search`, paginación). |
| POST | `/api/catalogos` | Crea un catálogo (único por cliente + producto) y una sesión inicial. |
| GET | `/api/catalogos/{id}` | Obtiene un catálogo por id. |
| GET | `/api/catalogos/{id}/final` | Devuelve la versión final aprobada (404 si no existe). |
| PATCH | `/api/catalogos/{id}` | Cambia estado a `CANCELADA` (solo si no hay versión final). |

### 4.1 Listar catálogos
```bash
curl -X GET "{{base}}/api/catalogos?cliente_id=1&estado=EN_PROCESO&with_final=false&page=1&per_page=20" \
     -H "Authorization: Bearer {{token}}"
```
*Filtros disponibles*
- `cliente_id`, `producto_id`: ids exactos.  
- `estado`: EN_PROCESO | CERRADA | CANCELADA.  
- `with_final`: true/false para filtrar si tienen versión final.  
- `search`: busca en nombre de cliente y producto (case-insensitive).

### 4.2 Crear catálogo
```bash
curl -X POST {{base}}/api/catalogos \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{
       "cliente_id":1,
       "producto_id":2,
       "etiqueta":"escenario principal"   # etiqueta de la sesión inicial (opcional)
     }'
```
Respuesta **201** incluye `id`, `estado` (EN_PROCESO) y `final_version_id=null`.

### 4.3 Obtener catálogo
```bash
curl -X GET {{base}}/api/catalogos/5 \
     -H "Authorization: Bearer {{token}}"
```

### 4.4 Versión final
```bash
curl -X GET {{base}}/api/catalogos/5/final \
     -H "Authorization: Bearer {{token}}"
# 200 -> snapshot de la versión aprobada
```
Si el catálogo aún no tiene final → **404**.

### 4.5 Cancelar catálogo
Solo posible si **NO** tiene versión final (`final_version_id=null`).
```bash
curl -X PATCH {{base}}/api/catalogos/5 \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{"estado":"CANCELADA"}'
```
*Reglas*:
- No puede cambiar a `CERRADA` manualmente (la asigna la aprobación de versión).  
- Si ya está `CERRADA` → solo lectura.  
- Si tiene final → no se permite cancelar.

---
## 5. Sesiones

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/catalogos/{catalogo_id}/sesiones` | Lista sesiones del catálogo (`is_active`, `with_current`, paginación). |
| POST | `/api/catalogos/{catalogo_id}/sesiones` | Crea una nueva sesión en el catálogo. |
| GET | `/api/sesiones/{id}` | Obtiene una sesión (`with_current=true` para incluir versión vigente). |
| PATCH | `/api/sesiones/{id}` | Edita etiqueta o `is_active`. |
| DELETE | `/api/sesiones/{id}` | Elimina la sesión (solo si no tiene versiones). |

### 5.1 Listar sesiones de un catálogo
```bash
curl -X GET "{{base}}/api/catalogos/5/sesiones?is_active=true&with_current=true&page=1&per_page=20" \
     -H "Authorization: Bearer {{token}}"
```

### 5.2 Crear sesión
```bash
curl -X POST {{base}}/api/catalogos/5/sesiones \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{"etiqueta":"escenario B"}'
```

### 5.3 Obtener sesión (incl. versión vigente)
```bash
curl -X GET "{{base}}/api/sesiones/10?with_current=true" \
     -H "Authorization: Bearer {{token}}"
```

### 5.4 Editar sesión
```bash
curl -X PATCH {{base}}/api/sesiones/10 \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{"etiqueta":"escenario B ajustado","is_active":false}'
```

### 5.5 Eliminar sesión
```bash
curl -X DELETE {{base}}/api/sesiones/10 \
     -H "Authorization: Bearer {{token}}"
```

---
## 6. Versiones

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/sesiones/{sesion_id}/versiones` | Lista versiones de la sesión (`estado`, `is_current`, paginación). |
| POST | `/api/sesiones/{sesion_id}/versiones` | Crea versión (snapshot) a partir del producto maestro. |
| GET | `/api/versiones/{id}` | Obtiene una versión por id. |
| PATCH | `/api/versiones/{id}` | Edita snapshot (solo en estados BORRADOR / ENVIADA). |
| POST | `/api/versiones/{id}/enviar` | Pasa de BORRADOR/CONTRAOFERTA → ENVIADA. |
| POST | `/api/versiones/{id}/contraoferta` | Marca ENVIADA → CONTRAOFERTA. |
| POST | `/api/versiones/{id}/rechazar` | Marca ENVIADA/CONTRAOFERTA → RECHAZADA. |
| POST | `/api/versiones/{id}/aprobar` | Marca ENVIADA/CONTRAOFERTA → APROBADA y `is_final=true` (cierra catálogo). |
| POST | `/api/versiones/{id}/current` | Fuerza la versión como vigente dentro de la sesión. |

### 6.1 Listar versiones de una sesión
```bash
curl -X GET "{{base}}/api/sesiones/10/versiones?is_current=true" \
     -H "Authorization: Bearer {{token}}"
```

### 6.2 Crear versión
```bash
curl -X POST {{base}}/api/sesiones/10/versiones \
     -H "Authorization: Bearer {{token}}" \
     -H "Content-Type: application/json" \
     -d '{"precio_exw":1.10,"porc_desc":0.07}'
```

### 6.3 Flujo de estados
```mermaid
stateDiagram-v2
    [*] --> BORRADOR
    BORRADOR --> ENVIADA : /enviar
    ENVIADA --> CONTRAOFERTA : /contraoferta
    CONTRAOFERTA --> ENVIADA : /enviar (nueva contraoferta)
    ENVIADA --> APROBADA : /aprobar
    CONTRAOFERTA --> APROBADA : /aprobar
    ENVIADA --> RECHAZADA : /rechazar
    CONTRAOFERTA --> RECHAZADA : /rechazar
```

### 6.4 Marcar vigente
```bash
curl -X POST {{base}}/api/versiones/42/current \
     -H "Authorization: Bearer {{token}}"
```

*Reglas importantes*
- Solo puede haber **una** `is_current=true` por sesión y **una** `is_final=true` por catálogo.  
- Aprobar (`/aprobar`) asigna `is_final=true`, copia el id a `catalogo.final_version_id` y cambia el estado del catálogo a `CERRADA`.  
- Cancelar catálogo no es posible si ya existe una versión final.

---
## 7. Variables de entorno útiles

| Variable | Ejemplo | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg2://user:pass@host/db` | Conexión producción |
| `TEST_DATABASE_URL` | `sqlite:///:memory:` | Sobre-escribe BD en tests |
| `SECRET_KEY` | `changeme` | Sesión Flask |
| `JWT_SECRET` | `changeme-too` | Firma de JWT |

---
## 8. Arranque rápido en dev
```bash
python -m venv venv
pip install -r requirements.txt
export FLASK_APP=wsgi.py
flask run  # http://127.0.0.1:5000
```

En producción usa un WSGI como **gunicorn**:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```