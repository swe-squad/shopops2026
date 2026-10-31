import hashlib
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.test_agent_core_contract import R, handler
from tests.test_demo_phone_auth import config, login

A = str(uuid.uuid4())
CONTENT = b"# Report\n"
ARTIFACT = {
    "id": A,
    "run_id": R,
    "filename": "report.md",
    "media_type": "text/markdown",
    "size": len(CONTENT),
    "sha256": hashlib.sha256(CONTENT).hexdigest(),
    "availability": "available",
}


@pytest.mark.parametrize("outcome", ["ok", "expired", "redirect", "oversize", "digest", "media"])
def test_scoped_downloads_bounded_and_safe(tmp_path, outcome):
    reads = []

    def transport(r):
        if r.url.path.endswith("/artifacts"):
            return httpx.Response(200, json={"items": [ARTIFACT], "next_cursor": None})
        if r.url.path.endswith("/content"):
            reads.append(r)
            if outcome == "expired":
                return httpx.Response(410)
            if outcome == "redirect":
                return httpx.Response(302, headers={"Location": "https://evil/secret"})
            data = {"oversize": b"x" * 1048577, "digest": b"x" * len(CONTENT)}.get(outcome, CONTENT)
            return httpx.Response(
                200,
                content=data,
                headers={"Content-Type": "text/html" if outcome == "media" else "text/markdown"},
            )
        return handler(r)

    with TestClient(create_app(config(tmp_path), httpx.MockTransport(transport))) as c:
        headers = login(c)
        assert c.get(f"/api/chat/artifacts/{A}/content", headers=headers).status_code == 404
        assert reads == []
        response = c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Report", "client_message_id": "stable-key", "output_mode": "report"},
        )
        assert "done" in response.text
        assert c.get(f"/api/chat/artifacts/{A}/content").status_code == 401
        result = c.get(f"/api/chat/artifacts/{A}/content", headers=headers)
        if outcome == "ok":
            assert result.content == CONTENT
            assert result.headers["x-content-type-options"] == "nosniff"
            assert result.headers["content-disposition"] == 'attachment; filename="report.md"'
        else:
            assert result.status_code == (410 if outcome == "expired" else 503)
        assert len(reads) == 1
        assert c.get("/api/chat/artifacts/foreign/content", headers=headers).status_code == 404
        assert len(reads) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"filename": "../secret.md"},
        {"media_type": "text/html"},
        {"size": 1048577},
        {"id": "../secret"},
    ],
)
def test_invalid_metadata_never_completes_or_allows_download(tmp_path, change):
    def transport(r):
        if r.url.path.endswith("/artifacts"):
            return httpx.Response(200, json={"items": [ARTIFACT | change], "next_cursor": None})
        return handler(r)

    with TestClient(create_app(config(tmp_path), httpx.MockTransport(transport))) as c:
        headers = login(c)
        result = c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Report", "client_message_id": "stable-key"},
        )
        assert '"type":"error"' in result.text
        assert '"type":"done"' not in result.text
        assert c.get(f"/api/chat/artifacts/{A}/content", headers=headers).status_code == 404


def test_report_answer_requires_authoritative_artifact(tmp_path):
    def transport(r):
        result = handler(r)
        if r.url.path == "/api/v1/runs/" + R:
            body = result.json()
            body["response"]["kind"] = "answer"
            return httpx.Response(200, json=body)
        return result

    with TestClient(create_app(config(tmp_path), httpx.MockTransport(transport))) as c:
        headers = login(c)
        response = c.post(
            "/api/chat/messages",
            headers=headers,
            json={"text": "Report", "output_mode": "report", "client_message_id": "stable-key"},
        )
        assert '"type":"done"' not in response.text
        assert '"type":"error"' in response.text
