def test_crear_y_listar_catalogo(client, auth_headers, seed_cliente_producto):
    # Crear catálogo
    payload = {
        "cliente_id": seed_cliente_producto["cliente_id"],
        "producto_id": seed_cliente_producto["producto_id"],
        "etiqueta": "default"
    }
    r = client.post("/api/catalogos", headers=auth_headers, json=payload)
    assert r.status_code == 201, r.text
    cat = r.get_json()
    assert cat["estado"] == "EN_PROCESO"
    assert cat["final_version_id"] is None
    catalogo_id = cat["id"]

    # Listar con filtro
    r = client.get(f"/api/catalogos?cliente_id={payload['cliente_id']}&producto_id={payload['producto_id']}&page=1&per_page=10",
                   headers=auth_headers)
    assert r.status_code == 200, r.text
    data = r.get_json()["data"]
    assert any(x["id"] == catalogo_id for x in data)

def test_catalogo_duplicado_conflict(client, auth_headers, seed_cliente_producto):
    body = {
        "cliente_id": seed_cliente_producto["cliente_id"],
        "producto_id": seed_cliente_producto["producto_id"],
    }
    r1 = client.post("/api/catalogos", headers=auth_headers, json=body)
    assert r1.status_code == 201, r1.text
    r2 = client.post("/api/catalogos", headers=auth_headers, json=body)
    assert r2.status_code == 409, r2.text  # único por cliente+producto

def test_cancelar_catalogo_sin_final(client, auth_headers, seed_cliente_producto):
    body = {"cliente_id": seed_cliente_producto["cliente_id"], "producto_id": seed_cliente_producto["producto_id"]}
    r1 = client.post("/api/catalogos", headers=auth_headers, json=body)
    assert r1.status_code == 201
    catalogo_id = r1.get_json()["id"]

    # Cancelar (válido si no tiene final)
    r2 = client.patch(f"/api/catalogos/{catalogo_id}", headers=auth_headers, json={"estado": "CANCELADA"})
    assert r2.status_code == 200, r2.text
    assert r2.get_json()["estado"] == "CANCELADA"
