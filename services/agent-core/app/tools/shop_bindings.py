"""Operator-owned versioned identity bindings, never populated from model arguments."""

import hashlib
import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.contracts.identity import Scope
from app.contracts.shop_data import BindingReference


class Binding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    version: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    tenant_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)
    shop_id: str = Field(min_length=1, max_length=128)
    phone: str = Field(pattern=r"^\+[0-9]{8,15}$", repr=False)
    shop_key: str = Field(pattern=r"^[a-zA-Z0-9_-]+:[a-zA-Z0-9_-]+$", max_length=128)
    coverage_start: str

    @field_validator("coverage_start")
    @classmethod
    def coverage_date(cls, value: str) -> str:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("invalid coverage date")
        return value

    @property
    def reference(self) -> BindingReference:
        digest = hashlib.sha256(
            json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return BindingReference(id=self.id, version=self.version, digest=digest)


class Bindings:
    def __init__(self, bindings: list[Binding]) -> None:
        self._bindings = {}
        for binding in bindings:
            key = (binding.id, binding.version)
            if key in self._bindings:
                raise ValueError("duplicate binding version")
            self._bindings[key] = binding

    @classmethod
    def load(cls, path: str) -> Bindings:
        try:
            data = json.loads(Path(path).read_text())
            if set(data) != {"bindings"} or not isinstance(data["bindings"], list):
                raise ValueError
            return cls([Binding.model_validate(value) for value in data["bindings"]])
        except OSError, ValueError, TypeError, KeyError:
            raise ValueError("invalid shop data bindings") from None

    def get(self, reference: BindingReference | None) -> Binding:
        if reference is None:
            raise ValueError("missing data binding")
        binding = self._bindings.get((reference.id, reference.version))
        if binding is None or binding.reference != reference:
            raise ValueError("data binding revision mismatch")
        return binding

    def resolve(self, reference: BindingReference | None, scope: Scope) -> Binding:
        binding = self.get(reference)
        if (binding.tenant_id, binding.user_id, binding.shop_id) != (
            scope.tenant_id,
            scope.user_id,
            scope.shop_id,
        ):
            raise ValueError("data binding scope mismatch")
        return binding
