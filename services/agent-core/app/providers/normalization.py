"""Validate public responses against the run's durable successful source references."""

from pydantic import ValidationError

from app.contracts.errors import InvalidOutput
from app.contracts.models import ApplicationResponse, Source


def normalize_response(
    value: dict | str | ApplicationResponse, persisted_sources: tuple[Source, ...]
) -> ApplicationResponse:
    try:
        response = (
            ApplicationResponse.model_validate_json(value)
            if isinstance(value, str)
            else ApplicationResponse.model_validate(value)
        )
    except ValidationError, ValueError, TypeError:
        raise InvalidOutput() from None
    allowed = {(source.type, source.reference) for source in persisted_sources}
    if not response.text.strip() or any(
        (source.type, source.reference) not in allowed for source in response.sources
    ):
        raise InvalidOutput()
    return response
