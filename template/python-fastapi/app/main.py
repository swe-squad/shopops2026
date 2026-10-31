from fastapi import FastAPI

SERVICE_NAME = "__SERVICE_NAME__"


def create_app() -> FastAPI:
    app = FastAPI(title=SERVICE_NAME)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"message": "pong", "service": SERVICE_NAME}

    return app


app = create_app()
