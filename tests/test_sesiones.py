
def crear_catalogo(client, headers, cliente_id, producto_id):
    r = client.post("/api/catalogos", headers=headers, json={
        "cliente_id": cliente_id, "producto_id": producto_id, "etiqueta": "default"
    })

    assert r.status_code == 201, r.text
    return r.get_json()["id"]

def test_crud_sesion(client, auth_headers, seed_cliente_producto):
    catalogo_id = crear_catalogo(client, auth_headers, seed_cliente_producto["cliente_id"], seed_cliente_producto["producto_id"])

    # Listar (sesión inicial creada por catalogo POST)
    r = client.get(f"/api/sesiones/catalogos/{catalogo_id}?with_current=true", headers=auth_headers)
    assert r.status_code == 200
    sesiones = r.get_json()["data"]
    assert len(sesiones) >= 1
    sesion_id = sesiones[0]["id"]

    # Crear nueva sesión
    r = client.post(f"/api/sesiones/catalogos/{catalogo_id}", headers=auth_headers, json={"etiqueta": "FOB"})
    assert r.status_code == 201
    sesion2_id = r.get_json()["id"]

    # Editar
    r = client.patch(f"/api/sesiones/{sesion2_id}", headers=auth_headers, json={"etiqueta": "Escenario B", "is_active": False})
    assert r.status_code == 200
    assert r.get_json()["etiqueta"] == "Escenario B"

    # Eliminar (válido porque no tiene versiones)
    r = client.delete(f"/api/sesiones/{sesion2_id}", headers=auth_headers)
    assert r.status_code == 200

def test_no_eliminar_sesion_con_versiones(client, auth_headers, seed_cliente_producto):
    catalogo_id = crear_catalogo(client, auth_headers, seed_cliente_producto["cliente_id"], seed_cliente_producto["producto_id"])
    # Crear sesión extra
    r = client.post(f"/api/sesiones/catalogos/{catalogo_id}", headers=auth_headers, json={"etiqueta": "Temp"})
    sesion_id = r.get_json()["id"]
    # Crear una versión en esa sesión
    r = client.post(f"/api/versiones/sesiones/{sesion_id}", headers=auth_headers, json={"cant_bultos": 3})
    assert r.status_code == 201

    # Intentar borrar -> 409
    r = client.delete(f"/api/sesiones/{sesion_id}", headers=auth_headers)
    assert r.status_code == 409, r.text
