class CoreError(Exception):
    code = "internal_error"
    retryable = False

    def __init__(self) -> None:
        super().__init__(self.code)


class NotFound(CoreError):
    code = "not_found"


class PermissionDenied(CoreError):
    code = "permission_denied"


class ConfigurationConflict(CoreError):
    code = "configuration_conflict"


class IdempotencyConflict(CoreError):
    code = "idempotency_conflict"


class ConversationBusy(CoreError):
    code = "conversation_busy"


class InvalidCursor(CoreError):
    code = "invalid_cursor"


class InvalidInput(CoreError):
    code = "invalid_input"


class InvalidTransition(CoreError):
    code = "invalid_transition"


class ProviderOutcomeUnknown(CoreError):
    code = "provider_outcome_unknown"


class InvalidOutput(CoreError):
    code = "invalid_output"


class ProviderRequestRejected(CoreError):
    code = "provider_request_rejected"


class ArtifactInvalid(CoreError):
    code = "artifact_invalid"


class ArtifactUnavailable(CoreError):
    code = "artifact_unavailable"


class ArtifactTransient(CoreError):
    code = "artifact_upstream_unavailable"
    retryable = True
