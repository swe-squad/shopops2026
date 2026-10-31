"""T07 implementation boundary; deliberately fails closed until its handoff."""

from app.contracts.runtime import RuntimeBundle, RuntimeProfile


def build_runtime_bundle(profile: RuntimeProfile) -> RuntimeBundle:
    raise NotImplementedError("T07 registered runtime bundle implementation is required")
