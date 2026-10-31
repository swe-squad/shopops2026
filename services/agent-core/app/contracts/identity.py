from pydantic import BaseModel, ConfigDict, Field


class Scope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tenant_id: str = Field(min_length=1, max_length=128)
    shop_id: str = Field(min_length=1, max_length=128)
    user_id: str = Field(min_length=1, max_length=128)


class AuthContext(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    tenant_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    shop_ids: frozenset[str]
    permissions: frozenset[str]

    def scope(self, shop_id: str) -> Scope:
        from app.contracts.errors import PermissionDenied

        if shop_id not in self.shop_ids:
            raise PermissionDenied()
        return Scope(tenant_id=self.tenant_id, shop_id=shop_id, user_id=self.user_id)
