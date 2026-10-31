"""T06 implementation boundary; deliberately fails closed until its handoff."""

from app.contracts.runtime import RuntimeBundle, RuntimeProfile


def build_hosted_environment(profile: RuntimeProfile, bundle: RuntimeBundle) -> dict:
    raise NotImplementedError("T06 hosted environment implementation is required")
