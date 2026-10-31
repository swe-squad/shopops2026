"""Run the real service with temporary persistence and an offline test provider."""

import importlib.util
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import uvicorn

ROOT = Path(__file__).resolve().parents[2]
kind = sys.argv[1]
if kind not in {"operations", "chat"}:
    raise SystemExit("Expected operations or chat")
service = "shopops-api" if kind == "operations" else "shopops-chat-api"
sys.path.insert(0, str(ROOT / "services" / service))

with TemporaryDirectory(prefix=f"shopops-browser-test-{kind}-") as directory:
    # Explicit dummy values override inherited environment; no real provider can be contacted.
    os.environ["SHOP_API_TOKEN"] = "workspace-browser-test-only"
    os.environ["SHOP_DATA_PATH"] = str(Path(directory) / "operations.sqlite3")
    os.environ["CHAT_DATA_PATH"] = str(Path(directory) / "chat.sqlite3")
    os.environ["OPENAI_API_KEY"] = "test-provider-key"
    os.environ["OPENAI_ORCHESTRATOR_AGENT_ID"] = "agent_browser_test_fixture"
    from app.main import create_app

    if kind == "operations":
        application = create_app()
    else:
        import httpx

        spec = importlib.util.spec_from_file_location("provider_fixture", Path(__file__).with_name("provider-fixture.py"))
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        application = create_app(transport=httpx.MockTransport(fixture.FixtureProvider()))
    uvicorn.run(application, host="127.0.0.1", port=8000 if kind == "operations" else 8001,
                log_level="warning", access_log=False)
