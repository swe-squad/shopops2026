"""ASGI factory requiring configuration before accepting traffic."""

from urllib.parse import urlparse

from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.auth import Authentication
from app.server import build_server
from app.service import DataService
from app.settings import Settings


def create_app():
    settings = Settings.load()
    service = DataService(settings)
    server = build_server(service)
    host = urlparse(settings.public_url).netloc
    hosts = [host]
    origins = [f"https://{host}"]
    if settings.internal_url:
        internal = urlparse(settings.internal_url)
        hosts.append(internal.netloc)
        origins.append(f"{internal.scheme}://{internal.netloc}")
    app = server.streamable_http_app(
        stateless_http=True,
        host="0.0.0.0",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=hosts,
            allowed_origins=origins,
        ),
    )

    async def health(request):
        return JSONResponse({"status": "ok"})

    async def ready(request):
        try:
            async with await service.db.connect() as conn:
                await conn.execute("SELECT 1 FROM mcp_control.results LIMIT 0")
            return JSONResponse(
                {
                    "status": "ready",
                    "ingestion_configured": bool(settings.ingestion_url),
                    "approval_configured": bool(settings.approval_url),
                }
            )
        except Exception:
            return JSONResponse({"status": "unavailable"}, status_code=503)

    app.routes.extend(
        [
            Route("/health", health),
            Route("/ready", ready),
        ]
    )
    return Authentication(app, settings)
