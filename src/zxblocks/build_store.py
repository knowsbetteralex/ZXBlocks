"""Immutable, classified builds and verified reuse for managed editor projects."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .compiler import compile_project
from .project_store import PROJECT_ID, now, write_json
from .runner import ARTIFACT_NAMES, BuildResult, build_project, require_tool


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compiler_fingerprint() -> str:
    fingerprint = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        fingerprint.update(source.name.encode())
        fingerprint.update(source.read_bytes())
    return fingerprint.hexdigest()


# Capture the version this process loaded. Editing files on disk must not label
# output from an already-running older compiler as output from the new version.
COMPILER_FINGERPRINT = compiler_fingerprint()


class BuildStore:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def directory(self, project_id: str, number: str | None = None) -> Path:
        if not re.fullmatch(PROJECT_ID, project_id) or (number is not None and not re.fullmatch(r"[0-9]{6}", number)):
            raise ValueError("Invalid build ID")
        path = self.root / project_id
        if number is not None:
            path /= number
        if not path.resolve().is_relative_to(self.root) or path.is_symlink():
            raise ValueError("Invalid build directory")
        return path

    def history(self, project_id: str) -> list[dict]:
        directory = self.directory(project_id)
        builds = []
        if directory.is_dir():
            for path in sorted(directory.iterdir(), reverse=True):
                if re.fullmatch(r"[0-9]{6}", path.name) and not path.is_symlink():
                    try:
                        builds.append(self.load(project_id, path.name))
                    except (ValueError, KeyError, OSError):
                        continue
        return builds

    def load(self, project_id: str, number: str) -> dict:
        manifest = json.loads((self.directory(project_id, number) / "build.json").read_text(encoding="utf-8"))
        if manifest.get("format") != "zxblocks/build/v1" or manifest.get("number") != number:
            raise ValueError("Invalid build manifest")
        return manifest

    def result(self, project_id: str, number: str) -> BuildResult:
        manifest = self.load(project_id, number)
        if manifest["status"] != "success":
            raise ValueError("This build did not succeed")
        result = BuildResult(self.directory(project_id, number), manifest["code_size"], organized=True)
        if any(not file.is_file() or digest(file) != manifest["hashes"].get(file.name) for file in result.files):
            raise ValueError("Build files are missing or changed. Build the project again.")
        return result

    def build(self, project_id: str, project: dict, assembler: str) -> tuple[dict, BuildResult, bool]:
        compile_project(project)
        executable = Path(require_tool(assembler))
        fingerprint = hashlib.sha256(json.dumps({"project": project, "compiler": COMPILER_FINGERPRINT,
            "assembler": digest(executable), "target": "spectrum48-sna/v1"}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        history = self.history(project_id)
        for manifest in history:
            if manifest.get("fingerprint") == fingerprint and manifest["status"] == "success":
                try:
                    return manifest, self.result(project_id, manifest["number"]), True
                except (ValueError, OSError):
                    pass  # Never reuse incomplete or edited artifacts.
        directory = self.directory(project_id)
        directory.mkdir(parents=True, exist_ok=True)
        # Include failed/incomplete jobs when allocating: old snapshots never change.
        number = 1 + max((int(path.name) for path in directory.iterdir() if re.fullmatch(r"[0-9]{6}", path.name)), default=0)
        if number > 999999:
            raise ValueError("Build history is full")
        job = self.directory(project_id, f"{number:06}")
        job.mkdir()
        manifest = {"format": "zxblocks/build/v1", "number": job.name, "created_at": now(),
                    "status": "building", "fingerprint": fingerprint, "name": project.get("name", "Project"),
                    "source_hash": hashlib.sha256(json.dumps(project, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()}
        write_json(job / "build.json", manifest)
        try:
            flat = build_project(project, job / "debug", assembler)
            result = BuildResult(job, flat.code_size, organized=True)
            for name in ARTIFACT_NAMES:
                destination = result.file(name)
                if destination != flat.file(name):
                    destination.parent.mkdir(exist_ok=True)
                    flat.file(name).replace(destination)
            manifest.update(status="success", code_size=result.code_size,
                            hashes={file.name: digest(file) for file in result.files})
            log = job / "debug" / "assembler.log"
            (job / "build.log").write_text((log.read_text(encoding="utf-8") if log.exists() else "") +
                                         f"\nBuilt {result.code_size} code bytes.\n", encoding="utf-8")
            write_json(job / "build.json", manifest)
            write_json(directory / "latest.json", {"number": job.name})
            return manifest, result, False
        except (ValueError, OSError) as exc:
            manifest.update(status="failed", error=str(exc))
            write_json(job / "build.json", manifest)
            (job / "build.log").write_text(str(exc) + "\n", encoding="utf-8")
            raise
