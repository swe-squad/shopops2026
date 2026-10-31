import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


def config(tmp_path, **extra):
    return Settings(
        "",
        "",
        "",
        str(tmp_path / "chat.db"),
        backend="agent_core",
        auth_mode="demo_phone",
        app_env="test",
        core_url="http://core:8000",
        core_shop="shop-a",
        core_revision="v1",
        shop_url="http://shop:8000",
        **extra,
    )


def login(client, phone="+84900000001"):
    response = client.post("/api/chat/auth/demo-phone", json={"phone_number": phone})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_phone_sessions_isolation_expiry_logout_and_no_provider(tmp_path):
    with TestClient(
        create_app(
            config(tmp_path),
            httpx.MockTransport(
                lambda r: httpx.Response(
                    200, json={"orchestrator_id": "orchestrator-1", "config_revision": "v1"}
                )
            ),
        )
    ) as c:
        assert c.get("/api/chat/auth/config").json() == {"mode": "demo_phone"}
        assert c.get("/api/chat/capabilities").status_code == 401
        a, b = login(c), login(c)
        assert a != b
        assert c.get("/api/chat/capabilities", headers=a).json() == {
            "report_mode": True,
            "artifacts": True,
        }
        assert c.post("/api/chat/auth/logout", headers=a).status_code == 204
        assert c.get("/api/chat/capabilities", headers=a).status_code == 401
        assert c.get("/api/chat/capabilities", headers=b).status_code == 200
        assert (
            c.post("/api/chat/auth/demo-phone", json={"phone_number": "+15559999999"}).status_code
            == 401
        )
        assert (
            c.post("/api/chat/auth/demo-phone", json={"phone_number": "15550000001"}).status_code
            == 422
        )
        assert (
            c.post(
                "/api/chat/auth/demo-phone", json={"phone_number": "+84900000001", "user_id": "bob"}
            ).status_code
            == 422
        )
        assert (
            c.post("/api/chat/auth/demo-phone", json={"phone_number": "+15550000002"}).status_code
            == 401
        )
        with c.app.state.core_store.connect() as db:
            assert (
                db.execute(
                    "SELECT count(*) FROM demo_sessions WHERE token_hash=?",
                    (b["Authorization"][7:],),
                ).fetchone()[0]
                == 0
            )
            db.execute("UPDATE demo_sessions SET expires=0")
        assert c.get("/api/chat/capabilities", headers=b).status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("app_env", "production"),
        ("core_url", ""),
        ("core_shop", ""),
        ("core_revision", ""),
        ("core_url", "https://public.cr.ngochoanielts.com"),
        ("core_url", "http://core/path"),
        ("auth_mode", "workspace_token"),
    ],
)
def test_core_config_fails_before_io(tmp_path, field, value):
    from dataclasses import replace

    with pytest.raises(RuntimeError):
        with TestClient(create_app(replace(config(tmp_path), **{field: value}))):
            pass


def test_each_login_starts_fresh_space_with_reusable_orchestrator_without_run(tmp_path):
    calls = []

    def provision(request):
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer local-alice"
        assert request.url.path == "/api/v1/shops/shop-a/orchestrator"
        return httpx.Response(
            200, json={"orchestrator_id": "orchestrator-1", "config_revision": "v1"}
        )

    with TestClient(create_app(config(tmp_path), httpx.MockTransport(provision))) as c:
        login(c)
        assert len(calls) == 1
        login(c)
        assert len(calls) == 2
        assert calls[0].content == calls[1].content
        with c.app.state.core_store.connect() as db:
            row = db.execute("SELECT orchestrator,conversation FROM core_spaces").fetchone()
            assert tuple(row) == ("orchestrator-1", None)
            assert db.execute("SELECT count(*) FROM core_spaces").fetchone()[0] == 2
