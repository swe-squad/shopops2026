"""Closed hosted request boundary; archive verification belongs to the bundle builder."""

import base64
from copy import deepcopy

from pydantic import ValidationError

from app.contracts.errors import ConfigurationConflict
from app.contracts.runtime import RuntimeBundle, RuntimeProfile


def build_hosted_environment(profile: RuntimeProfile, bundle: RuntimeBundle) -> dict:
    try:
        profile = RuntimeProfile.model_validate(profile.model_dump())
        if profile.environment_type != "openai_hosted" or (
            profile.bundle_id,
            profile.bundle_version,
            profile.bundle_sha256,
        ) != (bundle.bundle_id, bundle.bundle_version, bundle.bundle_sha256):
            raise ValueError()
        plugin = deepcopy(bundle.inline_plugin)
        if (
            set(plugin) != {"type", "name", "description", "source"}
            or plugin["type"] != "inline"
            or plugin["name"] != "shopops-analysis"
            or not isinstance(plugin["description"], str)
            or not plugin["description"].strip()
        ):
            raise ValueError()
        source = plugin["source"]
        if (
            set(source) != {"type", "media_type", "data"}
            or source["type"] != "base64"
            or source["media_type"] != "application/zip"
            or not isinstance(source["data"], str)
            or not source["data"]
            or len(source["data"]) > 524288
        ):
            raise ValueError()
        base64.b64decode(source["data"], validate=True)
    except ValidationError, ValueError, TypeError, KeyError:
        raise ConfigurationConflict() from None
    return {
        "type": "openai_hosted",
        "container_size": "small",
        "network": {"access": "disabled"},
        "plugins": [plugin],
    }
