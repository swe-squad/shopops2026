from collections.abc import Callable

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.contracts import AUTH_RESPONSES


class IncidentInput(BaseModel):
    title: str = Field(min_length=1, max_length=200, pattern=r".*\S.*")
    detail: str = Field(default="", max_length=2000)


class Incident(IncidentInput):
    id: int
    created_at: str


def router(connect: Callable, authorize: Callable) -> APIRouter:
    api = APIRouter(
        prefix="/api/operations", dependencies=[Depends(authorize)], responses=AUTH_RESPONSES
    )

    @api.get("/incidents", response_model=list[Incident])
    def list_incidents() -> list[dict]:
        with connect() as db:
            return [
                dict(row)
                for row in db.execute("SELECT * FROM incidents ORDER BY id DESC LIMIT 100")
            ]

    @api.post("/incidents", response_model=Incident, status_code=201)
    def create_incident(item: IncidentInput) -> dict:
        with connect() as db:
            cursor = db.execute(
                "INSERT INTO incidents (title, detail) VALUES (?, ?)",
                (item.title.strip(), item.detail),
            )
            return dict(
                db.execute("SELECT * FROM incidents WHERE id = ?", (cursor.lastrowid,)).fetchone()
            )

    return api
