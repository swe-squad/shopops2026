from fastapi import FastAPI

from app.api.common import install_errors

SERVICE_NAME = "mock-data-server"


def create_app() -> FastAPI:
    app = FastAPI(title=SERVICE_NAME)
    install_errors(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"message": "pong", "service": SERVICE_NAME}

    return app


app = create_app()
