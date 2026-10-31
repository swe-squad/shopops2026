import os
import time
import uuid

import httpx
import pytest


@pytest.fixture(scope="session")
def pair():
    return Pair()


class Pair:
    source_url = os.environ.get("PAIR_SOURCE_URL")
    processor_url = os.environ.get("PAIR_PROCESSOR_URL")

    def request(self, method, path, *, actor="+84900000001", source=False, key=None, **kwargs):
        url = self.source_url if source else self.processor_url
        assert url, "Run these tests through scripts/test-mock-pipeline.py"
        headers = {"X-Demo-User-Id": actor, "Idempotency-Key": key or uuid.uuid4().hex}
        return httpx.request(method, url + path, headers=headers, timeout=40, **kwargs)

    def wait(self, run_id):
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            response = self.request("GET", f"/v1/admin/sync-runs/{run_id}")
            assert response.status_code == 200, response.text
            run = response.json()
            if run["status"] in {"succeeded", "failed"}:
                return run
            time.sleep(0.1)
        pytest.fail("Synchronization did not finish")

    def write(self, method, path, **kwargs):
        response = self.request(method, path, **kwargs)
        assert response.status_code == 202, response.text
        result = response.json()
        run = self.wait(result["run_id"])
        assert run["status"] == "succeeded", run
        return result
