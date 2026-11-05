"""Explicit, non-mutating project format upgrades."""

from copy import deepcopy
from typing import Any

from .compiler import compile_project
from .formats import SUPPORTED_FORMATS


def upgrade_to_v2(project: Any) -> dict:
    """Validate an existing project and preserve its behavior in zxblocks/v2."""
    return upgrade_project(project, "zxblocks/v2")


def upgrade_project(project: Any, target: str = "zxblocks/v2") -> dict:
    """Validate, preserve legacy condition shapes, and never downgrade IR."""
    compile_project(project)
    if target not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported target format")
    if SUPPORTED_FORMATS.index(target) < SUPPORTED_FORMATS.index(project["format"]):
        raise ValueError("Downgrading project IR is not supported")
    upgraded = deepcopy(project)
    upgraded["format"] = target
    return upgraded
