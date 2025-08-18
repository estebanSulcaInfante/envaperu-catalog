def crear_catalogo_sesion(client, headers, cliente_id, producto_id):
    r = client.post("/api/catalogos", headers=headers, json={
        "cliente_id": cliente_id, "producto_id": producto_id, "etiqueta": "default"
    })
    assert r.status_code == 201
    catalogo_id = r.get_json()["id"]

    r = client.get(f"/api/sesiones/catalogos/{catalogo_id}", headers=headers)
    sesion_id = r.get_json()["data"][0]["id"]
    return catalogo_id, sesion_id

def test_flujo_version_basico(client, auth_headers, seed_cliente_producto):
    catalogo_id, sesion_id = crear_catalogo_sesion(client, auth_headers, seed_cliente_producto["cliente_id"], seed_cliente_producto["producto_id"])

    # Crear versión (snapshot)
    r = client.post(f"/api/versiones/sesiones/{sesion_id}", headers=auth_headers, json={
        "porc_desc": 0.10, "cant_bultos": 5, "observaciones": "Primera oferta"
    })
    assert r.status_code == 201, r.text
    v = r.get_json()
    version_id = v["id"]
    assert v["is_current"] is True
    assert v["estado"] == "BORRADOR"

    # Editar (permitido BORRADOR/ENVIADA)
    r = client.patch(f"/api/versiones/{version_id}", headers=auth_headers, json={"precio_exw": 11.50, "doc_x_paq": 12})
    assert r.status_code == 200

    # Enviar → Contraoferta → Aprobar
    r = client.post(f"/api/versiones/{version_id}/enviar", headers=auth_headers)
    assert r.status_code == 200
    r = client.post(f"/api/versiones/{version_id}/contraoferta", headers=auth_headers)
    assert r.status_code == 200
    r = client.post(f"/api/versiones/{version_id}/aprobar", headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()["is_final"] is True

    # Catálogo queda CERRADA y con final
    rc = client.get(f"/api/catalogos/{catalogo_id}", headers=auth_headers)
    assert rc.status_code == 200
    cat = rc.get_json()
    assert cat["estado"] == "CERRADA"
    assert cat["final_version_id"] == version_id

    # No se pueden crear más versiones en este catálogo
    r = client.post(f"/api/versiones/sesiones/{sesion_id}", headers=auth_headers, json={})
    assert r.status_code == 409

def test_rechazar_y_current(client, auth_headers, seed_cliente_producto):
    _, sesion_id = crear_catalogo_sesion(client, auth_headers, seed_cliente_producto["cliente_id"], seed_cliente_producto["producto_id"])

    # Crear v1 y ENVIAR
    r = client.post(f"/api/versiones/sesiones/{sesion_id}", headers=auth_headers, json={"cant_bultos": 2})
    v1 = r.get_json(); v1_id = v1["id"]
    client.post(f"/api/versiones/{v1_id}/enviar", headers=auth_headers)

    # Crear v2 (se vuelve current automáticamente)
    r = client.post(f"/api/versiones/sesiones/{sesion_id}", headers=auth_headers, json={"cant_bultos": 3})
    v2 = r.get_json(); v2_id = v2["id"]
    assert v2["is_current"] is True

    # Rechazar v1 (válido desde ENVIADA)
    r = client.post(f"/api/versiones/{v1_id}/rechazar", headers=auth_headers)
    assert r.status_code == 200

    # Forzar current a v1 (debería permitir porque no es final)
    r = client.post(f"/api/versiones/{v1_id}/current", headers=auth_headers)
    assert r.status_code == 200
    r = client.get(f"/api/versiones/{v1_id}", headers=auth_headers)
    assert r.get_json()["is_current"] is True
