"""Retired WorldBlueprint transport routes.

WorldGuard keeps target-object composition and qualification in memory.  A
portable JSON bundle, copied replay resources, materialization root, or
standalone package would create a second transport authority and is therefore
not part of the current product surface.  The former names remain as typed
fail-closed sentinels so stale callers receive a visible route error instead
of writing an artifact.
"""

from __future__ import annotations

from typing import Any

from .blueprint import BlueprintError


RETIREMENT_CODE = "WORLD_BLUEPRINT_NATIVE_DIRECTORY_ONLY"


def _retired(operation: str) -> None:
    raise BlueprintError(
        RETIREMENT_CODE,
        (
            f"WorldBlueprint {operation} is retired. Compose and validate the "
            "target-object model in memory under its native directory; no "
            "bundle, materialization, or standalone package is produced."
        ),
        details={"operation": operation, "transport_artifact": False},
    )


def build_world_blueprint_bundle(*args: Any, **kwargs: Any) -> None:
    """Reject the former bundle composition route explicitly."""

    _retired("bundle composition")


def write_world_blueprint_bundle(*args: Any, **kwargs: Any) -> None:
    """Reject disk export without touching the destination filesystem."""

    _retired("bundle export")


def load_world_blueprint_bundle(*args: Any, **kwargs: Any) -> None:
    """Reject loading a standalone object-DNA transport artifact."""

    _retired("bundle loading")


def verify_world_blueprint_bundle(*args: Any, **kwargs: Any) -> None:
    """Reject isolated bundle replay/materialization verification."""

    _retired("bundle verification")


def query_world_blueprint_bundle(*args: Any, **kwargs: Any) -> None:
    """Reject by-id queries against a retired transport artifact."""

    _retired("bundle query")


__all__ = [
    "RETIREMENT_CODE",
    "build_world_blueprint_bundle",
    "write_world_blueprint_bundle",
    "load_world_blueprint_bundle",
    "verify_world_blueprint_bundle",
    "query_world_blueprint_bundle",
]
