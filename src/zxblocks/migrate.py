"""Explicit, non-mutating project format upgrades."""

from copy import deepcopy
from typing import Any

from .compiler import compile_project


def upgrade_to_v2(project: Any) -> dict:
    """Validate an existing project and preserve its behavior in zxblocks/v2."""
    compile_project(project)
    upgraded = deepcopy(project)
    upgraded["format"] = "zxblocks/v2"
    return upgraded
