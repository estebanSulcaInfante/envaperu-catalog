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
El `access_token` sigue siendo válido hasta su expiración (por eso `/whoami` puede seguir funcionando inmediatamente después del logout).
```

### 1.4 Logout
```bash
curl -X POST {{base}}/api/auth/logout \
     -H "Content-Type: application/json" \
     -d '{"refresh_token":"4b8e..."}'
# 200 {"ok":true}
Logout revoca solo el `refresh_token` provisto (cierre de sesión de esa sesión). 

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
Al generar `imagen_key` se define la ruta/filename determinístico (slug + extensión).

```

2) **Subir archivo**  
```bash
curl -X POST {{base}}/api/productos/1/imagen/upload \
     -H "Authorization: Bearer {{token}}" \
     -F "file=@./foto.png"
El endpoint `/imagen/upload` sube el archivo al bucket privado `SUPABASE_BUCKET`
```

3) **Obtener URL firmada**  
```bash
curl -X GET "{{base}}/api/productos/1/imagen/url?expires_in=3600" \
     -H "Authorization: Bearer {{token}}"
# -> {"url":"https://...","expires_in":3600}
usando `SUPABASE_SERVICE_ROLE_KEY`. El endpoint `/imagen/url` devuelve una URL firmada temporal.
```

---
## 3. Clientes

El recurso **Cliente** representa la empresa o persona a la que se le vende un producto.

Campos devueltos por la API:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | int | Identificador interno |
| tipo_doc | str | Tipo de documento: `DNI`, `RUC`, `CE`, `PASAPORTE`, `OTRO` |
| num_doc | str | Número de documento |
| nombre | str | Razón social o nombre |
| descripcion | str \| null | Notas adicionales |
| pais | str \| null | Código ISO-2 (`PE`, `CL`, `CO`, …) |
| ciudad | str \| null | Ciudad |
| zona | str \| null | Zona / distrito |
| direccion | str \| null | Dirección física |
| clasificacion_riesgo | str | `ALTO`, `MEDIO` (por defecto) o `BAJO` |
| created_at | str | Fecha ISO-8601 de creación |

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/clientes` | Lista clientes (`search`, `pais`, `ciudad`, `page`, `per_page`). |
| POST | `/api/clientes` | Crea un cliente. |
| GET | `/api/clientes/{id}` | Obtiene un cliente por id. |
| PATCH | `/api/clientes/{id}` | Actualiza datos del cliente. |
| DELETE | `/api/clientes/{id}` | Elimina cliente (si no está referenciado). |

### 3.1 Listar clientes

`GET /api/clientes`

Respuesta 200:

```json
{
  "data": [
    {
      "id": 1,
      "tipo_doc": "RUC",
      "num_doc": "20123456789",
      "nombre": "Cliente S.A.",
      "descripcion": null,
      "pais": "PE",
      "ciudad": "Lima",
      "zona": null,
      "direccion": null,
      "clasificacion_riesgo": "MEDIO",
      "created_at": "2024-01-10T15:23:11Z"
    }
  ],
  "page": 1,
  "per_page": 20
}
```

### 3.2 Crear cliente

`POST /api/clientes`

Request:

```json
{
  "tipo_doc": "RUC",
  "num_doc": "20123456789",
  "nombre": "Cliente S.A.",
  "pais": "PE",
  "ciudad": "Lima"
}
```

Respuesta 201:

```json
{
  "id": 1,
  "tipo_doc": "RUC",
  "num_doc": "20123456789",
  "nombre": "Cliente S.A.",
  "descripcion": null,
  "pais": "PE",
  "ciudad": "Lima",
  "zona": null,
  "direccion": null,
  "clasificacion_riesgo": "MEDIO",
  "created_at": "2024-01-10T15:23:11Z"
}
```

### 3.3 Obtener cliente

`GET /api/clientes/{id}`

Respuesta 200: *idéntica al ejemplo de creación*

### 3.4 Editar cliente

`PATCH /api/clientes/{id}`

Request:

```json
{
  "ciudad": "Arequipa",
  "clasificacion_riesgo": "BAJO"
}
```

Respuesta 200:

```json
{
  "id": 1,
  "tipo_doc": "RUC",
  "num_doc": "20123456789",
  "nombre": "Cliente S.A.",
  "descripcion": null,
  "pais": "PE",
  "ciudad": "Arequipa",
  "zona": null,
  "direccion": null,
  "clasificacion_riesgo": "BAJO",
  "created_at": "2024-01-10T15:23:11Z"
}
```

### 3.5 Eliminar cliente

`DELETE /api/clientes/{id}`

Respuesta 200:

```json
{
  "ok": true
}
```

---
## 4. Catálogos

El recurso **Catálogo** vincula un *cliente* con un *producto* y consolida todas las negociaciones (sesiones y versiones) realizadas. Cada catálogo está en uno de estos estados:

* `EN_PROCESO` – negociación en curso (estado inicial).
* `CERRADA` – se aprobó una versión final.
* `CANCELADA` – se canceló manualmente (solo si no tiene versión final).

Campos devueltos por la API (`serialize_catalogo`):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | int | Identificador interno |
| cliente_id | int | Id del cliente |
| producto_id | int | Id del producto |
| estado | str | `EN_PROCESO`, `CERRADA`, `CANCELADA` |
| final_version_id | int \| null | Id de la versión final aprobada |
| created_at | str | ISO-8601 |
| cliente_nombre | str | Solo para conveniencia de UI |
| producto_nombre | str | Solo para conveniencia de UI |
| final_version | obj \| null | Resumen de la versión final (ver **Versiones**) |

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/catalogos` | Lista catálogos (`cliente_id`, `producto_id`, `estado`, `with_final`, `search`, `page`, `per_page`). |
| POST | `/api/catalogos` | Crea un nuevo catálogo + sesión inicial. |
| GET | `/api/catalogos/{id}` | Obtiene un catálogo por id. |
| GET | `/api/catalogos/{id}/final` | Devuelve la versión final (404 si no existe). |
| PATCH | `/api/catalogos/{id}` | Cambia estado a `CANCELADA` (solo si no tiene final). |

### 4.1 Listar catálogos

`GET /api/catalogos?cliente_id=1&estado=EN_PROCESO&page=1&per_page=20`

Respuesta 200:

```json
{
  "data": [
    {
      "id": 5,
      "cliente_id": 1,
      "producto_id": 2,
      "estado": "EN_PROCESO",
      "final_version_id": null,
      "created_at": "2024-02-03T10:15:20Z",
      "cliente_nombre": "Cliente S.A.",
      "producto_nombre": "Lapicero azul",
      "final_version": null
    }
  ],
  "page": 1,
  "per_page": 20
}
```

### 4.2 Crear catálogo

`POST /api/catalogos`

Request:

```json
{
  "cliente_id": 1,
  "producto_id": 2,
  "etiqueta": "escenario principal"
}
```

Respuesta 201:

```json
{
  "id": 6,
  "cliente_id": 1,
  "producto_id": 2,
  "estado": "EN_PROCESO",
  "final_version_id": null,
  "created_at": "2024-02-05T09:12:00Z",
  "cliente_nombre": "Cliente S.A.",
  "producto_nombre": "Lapicero azul",
  "final_version": null
}
```

### 4.3 Obtener catálogo

`GET /api/catalogos/{id}`

Respuesta 200: igual al objeto anterior.

### 4.4 Obtener versión final

`GET /api/catalogos/{id}/final`

Respuesta 200 (ejemplo simplificado):

```json
{
  "id": 42,
  "sesion_id": 10,
  "catalogo_id": 6,
  "producto_id": 2,
  "version_num": 3,
  "estado": "APROBADA",
  "is_current": true,
  "is_final": true,
  "um": "UNID",
  "precio_exw": 1.10,
  "porc_desc": 0.05,
  "subtotal_exw": 1050.0,
  "created_at": "2024-02-05T11:30:00Z"
  // …otros campos calculados omitidos para brevedad
}
```

Si el catálogo aún no tiene versión final ➜ **404**.

### 4.5 Cancelar catálogo

`PATCH /api/catalogos/{id}`

Request:

```json
{
  "estado": "CANCELADA"
}
```

Respuesta 200:

```json
{
  "id": 6,
  "cliente_id": 1,
  "producto_id": 2,
  "estado": "CANCELADA",
  "final_version_id": null,
  "created_at": "2024-02-05T09:12:00Z",
  "cliente_nombre": "Cliente S.A.",
  "producto_nombre": "Lapicero azul",
  "final_version": null
}
```

---
## 5. Sesiones

Una **Sesión** agrupa las diferentes **Versiones** de negociación de un catálogo. Puede estar activa o inactiva y opcionalmente exponer la versión vigente dentro de la sesión.

Campos devueltos por la API (`serialize_sesion`):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | int | Identificador interno |
| catalogo_id | int | Id del catálogo al que pertenece |
| etiqueta | str | Nombre descriptivo definido por usuario |
| is_active | bool | `true` si la sesión está abierta |
| created_at | str | ISO-8601 |
| current_version | obj \| null | Versión vigente (si se solicita con `with_current=true`) |

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/catalogos/{catalogo_id}/sesiones` | Lista sesiones (`is_active`, `with_current`, paginación). |
| POST | `/api/catalogos/{catalogo_id}/sesiones` | Crea una sesión nueva. |
| GET | `/api/sesiones/{id}` | Obtiene una sesión (`with_current=true` opcional). |
| PATCH | `/api/sesiones/{id}` | Edita etiqueta o `is_active`. |
| DELETE | `/api/sesiones/{id}` | Elimina la sesión (solo si no tiene versiones). |

### 5.1 Listar sesiones de un catálogo

`GET /api/catalogos/5/sesiones?is_active=true&with_current=true&page=1&per_page=20`

Respuesta 200:

```json
{
  "data": [
    {
      "id": 10,
      "catalogo_id": 5,
      "etiqueta": "escenario principal",
      "is_active": true,
      "created_at": "2024-02-05T09:30:00Z",
      "current_version": {
        "id": 40,
        "version_num": 2,
        "estado": "ENVIADA",
        "is_current": true,
        "is_final": false,
        "precio_exw": 1.15,
        "porc_desc": 0.04,
        "subtotal_exw": 920.0
      }
    }
  ],
  "page": 1,
  "per_page": 20
}
```

### 5.2 Crear sesión

`POST /api/catalogos/{catalogo_id}/sesiones`

Request:

```json
{
  "etiqueta": "escenario B"
}
```

Respuesta 201:

```json
{
  "id": 11,
  "catalogo_id": 5,
  "etiqueta": "escenario B",
  "is_active": true,
  "created_at": "2024-02-05T10:00:00Z",
  "current_version": null
}
```

### 5.3 Obtener sesión (incluyendo versión vigente)

`GET /api/sesiones/11?with_current=true`

Respuesta 200: (idéntico al objeto anterior, con `current_version` si existiera).

### 5.4 Editar sesión

`PATCH /api/sesiones/{id}`

Request:

```json
{
  "etiqueta": "escenario B ajustado",
  "is_active": false
}
```

Respuesta 200:

```json
{
  "id": 11,
  "catalogo_id": 5,
  "etiqueta": "escenario B ajustado",
  "is_active": false,
  "created_at": "2024-02-05T10:00:00Z",
  "current_version": null
}
```

### 5.5 Eliminar sesión

`DELETE /api/sesiones/{id}`

Respuesta 200:

```json
{
  "ok": true
}
```

---
## 6. Versiones

Una **Versión** es un snapshot de los datos de producto dentro de una sesión de negociación.

Estados posibles y transición:

- `BORRADOR` *(inicial)* → `ENVIADA` `/enviar`
- `ENVIADA` → `CONTRAOFERTA` `/contraoferta`
- `ENVIADA`/`CONTRAOFERTA` → `RECHAZADA` `/rechazar`
- `ENVIADA`/`CONTRAOFERTA` → `APROBADA` `/aprobar` (marca `is_final=true` y cierra catálogo)

Campos devueltos por la API (`_version_to_json`):

| Campo | Tipo | Descripción |
|-------|------|-------------|
| id | int | Identificador interno |
| sesion_id | int | Id de la sesión |
| catalogo_id | int | Id del catálogo |
| producto_id | int | Id del producto |
| version_num | int | Número de versión dentro de la sesión |
| estado | str | BORRADOR, ENVIADA, CONTRAOFERTA, RECHAZADA, APROBADA |
| is_current | bool | Versión vigente dentro de la sesión |
| is_final | bool | `true` si es la versión final aprobada |
| um, precio_exw, porc_desc, … | var | Snapshot de campos de producto y métricas calculadas |
| created_at | str | ISO-8601 |

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/sesiones/{sesion_id}/versiones` | Lista versiones (`estado`, `is_current`, paginación). |
| POST | `/api/sesiones/{sesion_id}/versiones` | Crea versión a partir del producto maestro. |
| GET | `/api/versiones/{id}` | Obtiene una versión. |
| PATCH | `/api/versiones/{id}` | Edita snapshot (estados BORRADOR, ENVIADA, CONTRAOFERTA). |
| POST | `/api/versiones/{id}/enviar` | Cambia BORRADOR → ENVIADA. |
| POST | `/api/versiones/{id}/contraoferta` | ENVIADA → CONTRAOFERTA. |
| POST | `/api/versiones/{id}/rechazar` | ENVIADA/CONTRAOFERTA → RECHAZADA. |
| POST | `/api/versiones/{id}/aprobar` | ENVIADA/CONTRAOFERTA → APROBADA (final & cierra catálogo). |
| POST | `/api/versiones/{id}/current` | Marca como vigente dentro de la sesión. |

### 6.1 Listar versiones de una sesión

`GET /api/sesiones/10/versiones?is_current=true`

Respuesta 200:

```json
{
  "data": [
    {
      "id": 40,
      "sesion_id": 10,
      "catalogo_id": 5,
      "producto_id": 2,
      "version_num": 2,
      "estado": "ENVIADA",
      "is_current": true,
      "is_final": false,
      "precio_exw": 1.15,
      "porc_desc": 0.04,
      "subtotal_exw": 920.0,
      "created_at": "2024-02-05T09:45:00Z"
    }
  ],
  "page": 1,
  "per_page": 20
}
```

### 6.2 Crear versión

`POST /api/sesiones/{sesion_id}/versiones`

Request:

```json
{
  "precio_exw": 1.10,
  "porc_desc": 0.07
}
```

Respuesta 201 (BORRADOR):

```json
{
  "id": 41,
  "sesion_id": 10,
  "catalogo_id": 5,
  "producto_id": 2,
  "version_num": 3,
  "estado": "BORRADOR",
  "is_current": false,
  "is_final": false,
  "precio_exw": 1.10,
  "porc_desc": 0.07,
  "subtotal_exw": 880.0,
  "created_at": "2024-02-05T10:00:00Z"
}
```

### 6.3 Cambios de estado

Ejemplo de enviar versión:

`POST /api/versiones/41/enviar`

Respuesta 200:

```json
{
  "id": 41,
  "estado": "ENVIADA",
  "is_current": false,
  "is_final": false,
  "created_at": "2024-02-05T10:00:00Z"
  /* …resto sin cambios */
}
```

Contraoferta, rechazar y aprobar devuelven el mismo objeto con `estado` actualizado y, en caso de aprobar, `is_final=true`.

### 6.4 Editar versión

`PATCH /api/versiones/{id}`

Request (solo BORRADOR/ENVIADA/CONTRAOFERTA):

```json
{
  "porc_desc": 0.05,
  "cant_bultos": 80
}
```

Respuesta 200: objeto versión actualizado.

### 6.5 Marcar vigente dentro de la sesión

`POST /api/versiones/{id}/current`

Respuesta 200: versión marcada `is_current=true`; todas las demás de la sesión pasan a `is_current=false`.

---
## 7. Variables de entorno útiles

| Variable                 | Ejemplo                                                    | Descripción                                   |
|--------------------------|------------------------------------------------------------|-----------------------------------------------|
| DATABASE_URL             | postgresql+psycopg://postgres:1234@localhost:5432/miapp   | Conexión a la BD principal                    |
| DATABASE_URL_TEST        | postgresql+psycopg://postgres:1234@localhost:5432/miapp_test | Conexión a la BD de tests (si no, usa SQLite) |
| SECRET_KEY               | changeme                                                   | Llave de sesión Flask                         |
| JWT_SECRET               | changeme-too                                               | Firma de JWT                                  |
| SUPABASE_URL             | https://xxx.supabase.co                                   | URL del proyecto Supabase                     |
| SUPABASE_SERVICE_ROLE_KEY| eyJhbGciOiJI...                                           | Service Role Key para subir/firmar            |
| SUPABASE_BUCKET          | product-images                                            | Bucket privado para imágenes de productos     |

> Nota: instala `python-dotenv` si quieres que Flask cargue automáticamente tu `.env`.

---
## 8. Arranque rápido en dev

python -m venv venv
venv\Scripts\pip install -r requirements.txt

# Crear base de datos si no existe (Postgres)
# Linux/Mac:
createdb miapp || true
# Windows (psql):
psql -U postgres -h localhost -c "CREATE DATABASE miapp;" || REM ya existe

# Variables de entorno (ejemplos)
# Linux/Mac (bash/zsh):
export FLASK_APP=wsgi.py
export DATABASE_URL=postgresql+psycopg://postgres:1234@localhost:5432/miapp

# Windows PowerShell:
$env:FLASK_APP="wsgi.py"
$env:DATABASE_URL="postgresql+psycopg://postgres:1234@localhost:5432/miapp"

# Windows CMD:
set FLASK_APP=wsgi.py
set DATABASE_URL=postgresql+psycopg://postgres:1234@localhost:5432/miapp

flask run  # http://127.0.0.1:5000


En producción usa un WSGI como **gunicorn**:
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```