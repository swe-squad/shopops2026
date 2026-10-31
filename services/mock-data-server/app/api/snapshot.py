from typing import Literal

from fastapi import FastAPI
from pydantic import AwareDatetime, BaseModel, Field

from app.domain.entities import Membership, Merchant, User
from app.storage.snapshot import snapshot


class AccessRows(BaseModel):
    users: list[User]
    merchants: list[Merchant]
    merchant_memberships: list[Membership]


class Document(BaseModel):
    document_id: str
    merchant_id: str
    platform: Literal["shopee-open-platform", "lazada", "shopify"]
    shop_id: str
    resource: Literal["orders", "order_items", "supplement"]
    source_kind: Literal["api_subset", "provisional_api_subset", "demo_supplement"]
    captured_at: str
    resource_revision: int = Field(ge=0)
    payload: dict


class Tombstone(BaseModel):
    tombstone_id: int
    revision: int
    resource: str
    record_key: dict
    scope: dict
    deleted_at: AwareDatetime


class Snapshot(BaseModel):
    schema_version: Literal["1.0"]
    source_revision: int
    complete: Literal[True]
    as_of: str
    access: AccessRows
    documents: list[Document]
    tombstones: list[Tombstone]
    counts: dict[str, int]


def register(app: FastAPI) -> None:
    app.add_api_route("/v1/snapshot", snapshot, methods=["GET"], response_model=Snapshot)
