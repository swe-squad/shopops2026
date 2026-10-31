from app.contracts.errors import CoreError, PermissionDenied
from app.contracts.identity import AuthContext


class Unauthorized(CoreError):
    code = "unauthorized"


def require_permission(auth: AuthContext, permission: str) -> None:
    if permission not in auth.permissions:
        raise PermissionDenied()
