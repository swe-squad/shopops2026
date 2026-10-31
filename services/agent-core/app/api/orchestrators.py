from fastapi import APIRouter, Depends, Response

from app.api.schemas import ProvisionInput, ProvisionOutput
from app.auth.dependencies import require_permission
from app.contracts.errors import NotFound
from app.contracts.identity import AuthContext
from app.contracts.repository import Repository


def shop_scope(auth: AuthContext, shop_id: str):
    if shop_id not in auth.shop_ids:
        raise NotFound()
    return auth.scope(shop_id)


def add_orchestrators(router: APIRouter, repository: Repository, identity) -> None:
    auth_dependency = Depends(identity)

    @router.post("/shops/{shop_id}/orchestrator", response_model=ProvisionOutput)
    async def provision(
        shop_id: str,
        body: ProvisionInput,
        response: Response,
        auth: AuthContext = auth_dependency,
    ):
        scope = shop_scope(auth, shop_id)
        require_permission(auth, "orchestrator:provision")
        result = await repository.provision(scope, body.template_id, body.config_revision)
        response.status_code = 201 if result.created else 200
        return ProvisionOutput(
            orchestrator_id=result.record.id, config_revision=result.record.config_revision
        )
