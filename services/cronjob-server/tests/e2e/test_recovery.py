import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

import httpx


def control(**changes):
    return httpx.post(os.environ["PAIR_PROXY_URL"] + "/__test/state", json=changes).json()


def await_flag(name):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if httpx.get(os.environ["PAIR_PROXY_URL"] + "/__test/state").json()[name]:
            return
        time.sleep(0.1)
    raise AssertionError(f"Fault injector did not reach {name}")


def docker(action, name):
    assert name.startswith("shopops-pair-")
    subprocess.run(["docker", action, name], capture_output=True, check=True)


def await_ready(pair):
    binding = subprocess.check_output(
        ["docker", "port", os.environ["PAIR_PROCESSOR_CONTAINER"], "8000/tcp"], text=True
    ).strip()
    pair.processor_url = "http://" + binding
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            if pair.request("GET", "/health/ready").status_code == 200:
                return
        except httpx.RequestError:
            pass
        time.sleep(0.2)
    raise AssertionError("Processor did not restart")


def test_committed_source_mutation_recovers_after_processor_crash(pair):
    pair.write("POST", "/v1/sync-runs", json={})
    before = pair.request("GET", "/v1/snapshot", source=True).json()["source_revision"]
    control(hold_mutations=True, mutation_committed=False)
    processor = os.environ["PAIR_PROCESSOR_CONTAINER"]
    params = {"shop_key": "lazada:1001", "sku": "SHIRT-M"}
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            pair.request,
            "PATCH",
            "/v1/mock/products/record",
            params=params,
            json={"name": "Recovered mutation"},
            key="crash-after-source-commit",
        )
        try:
            await_flag("mutation_committed")
            runs = pair.request("GET", "/v1/admin/sync-runs", params={"limit": 200}).json()["data"]
            run_id = next(r["run_id"] for r in reversed(runs) if r["status"] == "pending_mutation")
            docker("kill", processor)
        finally:
            control(hold_mutations=False)
            docker("start", processor)
        try:
            future.result()
        except httpx.RequestError:
            pass
    await_ready(pair)
    assert pair.wait(run_id)["status"] == "succeeded"
    after = pair.request("GET", "/v1/snapshot", source=True).json()["source_revision"]
    assert after == before + 1
    replay = pair.request(
        "PATCH",
        "/v1/mock/products/record",
        params=params,
        json={"name": "Recovered mutation"},
        key="crash-after-source-commit",
    )
    assert replay.json()["run_id"] == run_id
    assert (
        pair.request("GET", "/v1/core/products/record", params=params).json()["data"]["name"]
        == "Recovered mutation"
    )


def test_invalid_snapshot_keeps_previous_publication(pair):
    pair.write("POST", "/v1/sync-runs", json={})
    before = pair.request("GET", "/v1/core/orders").json()
    control(corrupt_snapshot=True)
    try:
        response = pair.request("POST", "/v1/sync-runs", json={})
        run = pair.wait(response.json()["run_id"])
        assert run["status"] == "failed" and run["attempts"] == 1
        assert pair.request("GET", "/v1/core/orders").json() == before
    finally:
        control(corrupt_snapshot=False)


def test_edit_during_snapshot_requires_later_run(pair):
    control(hold_snapshots=True, snapshot_captured=False)
    params = {"shop_key": "lazada:1001", "sku": "SHIRT-M"}
    before = pair.request("GET", "/v1/mock/products/record", params=params).json()["data"]["name"]
    try:
        first = pair.request("POST", "/v1/sync-runs", json={}).json()
        await_flag("snapshot_captured")
        mutation = pair.request(
            "PATCH",
            "/v1/entities/products/record",
            source=True,
            params=params,
            json={"name": "After snapshot"},
        )
        assert mutation.status_code == 200
    finally:
        control(hold_snapshots=False)
    assert pair.wait(first["run_id"])["status"] == "succeeded"
    assert (
        pair.request("GET", "/v1/core/products/record", params=params).json()["data"]["name"]
        == before
    )
    pair.write("POST", "/v1/sync-runs", json={})
    assert (
        pair.request("GET", "/v1/core/products/record", params=params).json()["data"]["name"]
        == "After snapshot"
    )


def test_source_outage_fails_closed_without_affecting_liveness(pair):
    source = os.environ["PAIR_SOURCE_CONTAINER"]
    docker("stop", source)
    try:
        assert pair.request("GET", "/v1/core/orders").status_code == 503
        assert pair.request("GET", "/health/live").status_code == 200
    finally:
        docker("start", source)
    binding = subprocess.check_output(["docker", "port", source, "8000/tcp"], text=True).strip()
    pair.source_url = "http://" + binding
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            if pair.request("GET", "/health/ready", source=True).status_code == 200:
                break
        except httpx.RequestError:
            pass
        time.sleep(0.2)
    assert pair.request("GET", "/v1/core/orders").status_code == 200


def test_membership_removal_hides_historical_raw_and_other_users_runs(pair):
    pair.write("POST", "/v1/sync-runs", json={})
    phone = "+84900000010"
    rows = pair.request("GET", "/v1/raw/documents", actor=phone).json()["data"]
    assert rows
    own_run = pair.write("POST", "/v1/sync-runs", json={}, actor=phone)
    assert (
        pair.request("GET", f"/v1/sync-runs/{own_run['run_id']}", actor="+84900000009").status_code
        == 404
    )
    grants = pair.request("GET", "/v1/access", source=True, params={"user_id": phone}).json()
    response = pair.request(
        "DELETE",
        "/v1/admin/entities/merchant-memberships/record",
        source=True,
        params={"user_id": phone, "merchant_id": grants["merchant_ids"][0]},
    )
    assert response.status_code == 200
    assert (
        pair.request(
            "GET",
            "/v1/raw/documents/record",
            actor=phone,
            params={"document_id": rows[0]["document_id"]},
        ).status_code
        == 404
    )
    assert pair.request("GET", "/v1/core/orders", actor=phone).json()["pagination"]["total"] == 0
    assert (
        pair.request("GET", f"/v1/sync-runs/{own_run['run_id']}", actor=phone).json()["shop_counts"]
        == {}
    )


def test_runtime_logs_omit_credentials_and_phone_ids(pair):
    for variable in ("PAIR_SOURCE_CONTAINER", "PAIR_PROCESSOR_CONTAINER"):
        logs = subprocess.run(
            ["docker", "logs", os.environ[variable]], text=True, capture_output=True, check=True
        )
        combined = logs.stdout + logs.stderr
        contains_sensitive = "+849" in combined or os.environ["POSTGRES_PASSWORD"] in combined
        assert not contains_sensitive, "Runtime logs must omit sensitive values"
