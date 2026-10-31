import uuid


def test_seed_sync_and_shared_reads(pair):
    snapshot = pair.request("GET", "/v1/snapshot", source=True).json()
    assert snapshot["counts"]["users"] == 10
    assert snapshot["counts"]["orders"] == 140
    pair.write("POST", "/v1/sync-runs", json={})
    for n in range(1, 11):
        response = pair.request("GET", "/v1/core/orders", actor=f"+849000000{n:02}")
        assert response.status_code == 200, response.text
        assert response.json()["pagination"]["total"] == 20
    first = pair.request("GET", "/v1/core/orders", actor="+84900000005").json()
    second = pair.request("GET", "/v1/core/orders", actor="+84900000006").json()
    assert first == second


def test_every_entity_crud_through_facade(pair):
    phone, merchant, shop = "+84999999999", "e2e-merchant", "shopee-open-platform:9001"
    admin = "/v1/admin/mock/"
    business = "/v1/mock/"
    entries = [
        (
            "users",
            {"user_id": phone, "display_name": "E2E", "is_active": True},
            {"display_name": "Edited"},
            ("user_id",),
        ),
        (
            "merchants",
            {"merchant_id": merchant, "name": "E2E", "is_active": True},
            {"name": "Edited"},
            ("merchant_id",),
        ),
        (
            "merchant-memberships",
            {"user_id": phone, "merchant_id": merchant, "role": "owner", "is_active": True},
            {"role": "analyst"},
            ("user_id", "merchant_id"),
        ),
    ]
    resources = [
        ("shops", {"name": "Edited"}, ("shop_key",)),
        ("products", {"unit_cost": "25000.00"}, ("shop_key", "sku")),
        ("promotions", {"name": "Edited"}, ("shop_key", "promotion_id")),
        ("orders", {"seller_discount": "10.00"}, ("shop_key", "order_id")),
        ("order-items", {"quantity": 2}, ("shop_key", "order_id", "line_id")),
        ("reviews", {"body": "Edited"}, ("shop_key", "review_id")),
        ("returns", {"reason": "Edited"}, ("shop_key", "return_id")),
        ("inventory", {"available": 50}, ("shop_key", "sku", "location_id", "observed_at")),
        ("settlements", {"fee_amount": "123.00"}, ("shop_key", "order_id")),
        ("fulfillment", {"deadline_basis": "Edited"}, ("shop_key", "order_id")),
        ("account-health", {"reason": "Edited"}, ("shop_key", "event_id")),
    ]
    templates = {}
    for name, patch, keys in resources:
        rows = pair.request(
            "GET", business + name, params={"shop_key": "shopee-open-platform:1001", "limit": 200}
        ).json()["data"]
        if name == "orders":
            row = next(r for r in rows if r["order_id"] == "100000")
        elif name in {"order-items", "reviews", "returns", "settlements", "fulfillment"}:
            row = dict(rows[0])
            row["order_id"] = "100000"
        else:
            row = dict(rows[0])
        row["shop_key"] = shop
        if name == "shops":
            row.update(merchant_id=merchant, source_shop_id="9001")
        if name == "orders":
            row["promotion_id"] = templates["promotions"]["promotion_id"]
        if "sku" in row and name != "products":
            row["sku"] = templates["products"]["sku"]
        if name == "order-items":
            row["status"] = templates["orders"]["status"]
        templates[name] = row
        entries.append((name, row, patch, keys))
    for i, (name, body, patch, keys) in enumerate(entries):
        path = (admin if i < 3 else business) + name
        result = pair.write("POST", path, json=body, actor=phone)
        key = {k: body[k] for k in keys}
        response = pair.request("GET", path + "/record", params=key, actor=phone)
        assert response.status_code == 200, response.text
        pair.write("PATCH", path + "/record", params=key, json=patch, actor=phone)
        if i >= 3:
            response = pair.request("GET", f"/v1/core/{name}/record", params=key, actor=phone)
            assert response.status_code == 200, response.text
            assert response.json()["applied_source_revision"] >= result["source_revision"]
    for i in reversed(range(len(entries))):
        name, body, _, keys = entries[i]
        path = (admin if i < 3 else business) + name
        pair.write("DELETE", path + "/record", params={k: body[k] for k in keys}, actor=phone)


def test_encoded_shopify_id_and_idempotency(pair):
    key = uuid.uuid4().hex
    params = {"shop_key": "shopify:1001", "order_id": "gid://shopify/Order/100000"}
    response = pair.write(
        "PATCH",
        "/v1/mock/orders/record",
        params=params,
        json={"seller_discount": "123.00"},
        key=key,
    )
    replay = pair.request(
        "PATCH",
        "/v1/mock/orders/record",
        params=params,
        json={"seller_discount": "123.00"},
        key=key,
    )
    assert replay.status_code == 202
    assert replay.json()["run_id"] == response["run_id"]
    core = pair.request("GET", "/v1/core/orders/record", params=params).json()["data"]
    assert core["seller_discount"] == "123.00"
