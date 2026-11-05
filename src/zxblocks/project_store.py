"""Small filesystem project store. Editor documents are separate from compiler IR."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .compiler import compile_project
from .formats import SUPPORTED_FORMATS

PROJECT_ID = r"[0-9a-f]{32}"


class RevisionConflict(ValueError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def write_json(path: Path, value: Any) -> None:
    """Replace a complete JSON file atomically, never truncate a saved document."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def validate_document(document: Any) -> None:
    if not isinstance(document, dict) or document.get("format") != "zxblocks/editor/v2":
        raise ValueError("Expected a zxblocks/editor/v2 document")
    if set(document) - {"format", "metadata", "workspace", "view", "project"}:
        raise ValueError("Unknown editor document fields")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict) or set(metadata) != {"name", "format", "initials"}:
        raise ValueError("Invalid editor metadata")
    if not isinstance(metadata["name"], str) or len(metadata["name"]) > 120:
        raise ValueError("Project name must contain at most 120 characters")
    if metadata["format"] not in SUPPORTED_FORMATS or not isinstance(metadata["initials"], dict):
        raise ValueError("Invalid editor format or initial values")
    if not isinstance(document.get("workspace"), dict) or not isinstance(document.get("view", {}), dict):
        raise ValueError("Invalid workspace or viewport")
    # A draft may have disconnected/incomplete blocks and therefore no IR.
    project = document.get("project")
    if project is not None:
        compile_project(project)
        if project.get("name") != metadata["name"] or project.get("format") != metadata["format"]:
            raise ValueError("Editor metadata and project IR disagree")


class ProjectStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def directory(self, project_id: str) -> Path:
        if not re.fullmatch(PROJECT_ID, project_id):
            raise ValueError("Invalid project ID")
        path = self.root / project_id
        if path.is_symlink() or path.resolve().parent != self.root:
            raise ValueError("Invalid project directory")
        return path

    def load(self, project_id: str) -> dict:
        record = json.loads((self.directory(project_id) / "workspace.json").read_text(encoding="utf-8"))
        if record.get("format") != "zxblocks/stored-project/v1" or record.get("id") != project_id:
            raise ValueError("Invalid saved project")
        validate_document(record["document"])
        return record

    @staticmethod
    def summary(record: dict) -> dict:
        return {"id": record["id"], "name": record["document"]["metadata"]["name"] or "Без названия",
                "revision": record["revision"], "updated_at": record["updated_at"],
                "valid": record["document"].get("project") is not None}

    def list(self) -> list[dict]:
        records = []
        if self.root.is_dir():
            for path in self.root.iterdir():
                if re.fullmatch(PROJECT_ID, path.name) and not path.is_symlink():
                    # A damaged project must not hide all the healthy projects.
                    try:
                        records.append(self.summary(self.load(path.name)))
                    except (ValueError, KeyError, OSError):
                        continue
        return sorted(records, key=lambda item: item["updated_at"], reverse=True)

    def create(self, document: dict) -> dict:
        validate_document(document)
        project_id = uuid.uuid4().hex
        timestamp = now()
        record = {"format": "zxblocks/stored-project/v1", "id": project_id, "revision": 1,
                  "created_at": timestamp, "updated_at": timestamp, "document": document}
        self._write(record)
        return record

    def save(self, project_id: str, document: dict, revision: int) -> dict:
        validate_document(document)
        record = self.load(project_id)
        if type(revision) is not int or revision != record["revision"]:
            raise RevisionConflict("Проект изменён в другой вкладке. Откройте его заново или создайте копию через меню.")
        record.update(document=document, revision=revision + 1, updated_at=now())
        self._write(record)
        return record

    def _write(self, record: dict) -> None:
        directory = self.directory(record["id"])
        # workspace.json is authoritative; project.json is a derived CLI export.
        # Write the export first: a failed save must never acknowledge a new revision.
        project = record["document"].get("project")
        if project is None:
            (directory / "project.json").unlink(missing_ok=True)
        else:
            write_json(directory / "project.json", project)
        write_json(directory / "workspace.json", record)
