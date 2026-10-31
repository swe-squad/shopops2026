from pydantic import BaseModel


class ErrorDetail(BaseModel):
    detail: str


AUTH_RESPONSES = {401: {"model": ErrorDetail, "description": "Missing or invalid workspace token."}}
