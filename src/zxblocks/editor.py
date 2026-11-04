"""Loopback-only editor host and compiler API; no third-party Python packages."""

from __future__ import annotations

import json
import re
import socket
import threading
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from .compiler import CompileError, compile_project
from .build_store import BuildStore
from .project_store import PROJECT_ID, ProjectStore, RevisionConflict
from .runner import ARTIFACT_NAMES, build_project, launch_emulator, require_tool

MAX_REQUEST_BYTES = 1024 * 1024
EDITOR_DIST = Path(__file__).resolve().parents[2] / "editor" / "dist"
EDITOR_BUILDS = Path(__file__).resolve().parents[2] / "build" / "editor"
PROJECTS_ROOT = Path(__file__).resolve().parents[2] / "projects"


class EditorHTTPServer(ThreadingHTTPServer):
    allow_reuse_port = False

    def server_bind(self) -> None:
        # Windows SO_REUSEADDR permits two active listeners on the same port.
        # An exclusive listener prevents requests reaching an old compiler.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.allow_reuse_address = False
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class EditorHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".js": "text/javascript"}

    def _json(self, status: int, value: dict) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                self._json(413, {"error": {"message": "Project must be 1 byte to 1 MiB", "path": None}})
                return
            # Consume bounded request data before rejecting an endpoint/origin.
            # Closing with unread uploads can turn JSON errors into TCP resets
            # on Windows. One extra byte covers the size-limit boundary.
            self.connection.settimeout(5)
            body = self.rfile.read(min(length, MAX_REQUEST_BYTES + 1))
        except (ValueError, OSError) as exc:
            self._json(400, {"error": {"message": str(exc), "path": None}})
            return
        managed = re.fullmatch(rf"/api/projects(?:/({PROJECT_ID})/(save|build|run|builds/([0-9]{{6}})/run))?", self.path)
        if self.path not in ("/api/compile", "/api/build", "/api/run") and not managed:
            self._json(404, {"error": {"message": "Unknown endpoint", "path": None}})
            return
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.server.server_port}",
                   f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed:
            self._json(403, {"error": {"message": "Same-origin requests only", "path": None}})
            return
        try:
            if length > MAX_REQUEST_BYTES:
                self._json(413, {"error": {"message": "Project must be 1 byte to 1 MiB", "path": None}})
                return
            project = json.loads(body.decode("utf-8"))
            if managed:
                with self.server.operation_lock:
                    result = self._project_post(managed, project)
                self._json(200, result)
                return
            asm = compile_project(project)
            if self.path == "/api/compile":
                self._json(200, {"asm": asm})
                return
            with self.server.operation_lock:
                launch = self.path == "/api/run"
                if launch:
                    require_tool(self.server.emulator)
                job = uuid.uuid4().hex
                # Fresh directory per request: running snapshots are immutable,
                # and no client-supplied filename or path is accepted.
                result = build_project(project, self.server.build_root / job, self.server.assembler)
                process = launch_emulator(result, self.server.emulator) if launch else None
                if process:
                    self.server.emulator_processes = [p for p in self.server.emulator_processes if p.poll() is None]
                    self.server.emulator_processes.append(process)
                self.server.builds[job] = result
            self._json(200, {
                "asm": asm, "code_size": result.code_size, "launched": launch,
                "artifacts": {file.suffix[1:]: f"/api/artifacts/{job}/{file.name}" for file in result.files},
            })
        except RevisionConflict as exc:
            self._json(409, {"error": {"message": str(exc), "path": None}})
        except (CompileError, ValueError, UnicodeError, RecursionError, OSError, KeyError, TypeError) as exc:
            self._json(400, {"error": {"message": str(exc), "path": getattr(exc, "path", None)}})

    def _project_post(self, match: re.Match, body: dict) -> dict:
        if not isinstance(body, dict):
            raise ValueError("Expected a JSON object")
        project_id, action, number = match.groups()
        store = self.server.projects
        if not project_id:
            return store.create(body["document"])
        store.load(project_id)  # Operations always belong to a real project.
        if action == "save":
            return store.save(project_id, body["document"], body["revision"])
        launch = action == "run" or number is not None
        if launch:
            require_tool(self.server.emulator)
        if number:
            result = self.server.project_builds.result(project_id, number)
            manifest = self.server.project_builds.load(project_id, number)
            reused = True
        else:
            manifest, result, reused = self.server.project_builds.build(project_id, body["project"], self.server.assembler)
        if launch:
            process = launch_emulator(result, self.server.emulator)
            self.server.emulator_processes = [p for p in self.server.emulator_processes if p.poll() is None]
            self.server.emulator_processes.append(process)
        return {"asm": result.file("project.asm").read_text(encoding="utf-8"),
                "code_size": result.code_size, "launched": launch, "reused": reused,
                "build": self._build_summary(project_id, manifest)}

    @staticmethod
    def _build_summary(project_id: str, manifest: dict) -> dict:
        number = manifest["number"]
        result = {key: manifest[key] for key in ("number", "created_at", "status", "name", "code_size", "error", "source_hash") if key in manifest}
        prefix = f"/api/projects/{project_id}/builds/{number}"
        result["log"] = prefix + "/build.log"
        if manifest["status"] == "success":
            result["artifacts"] = {name.split(".")[1]: f"{prefix}/{name}" for name in ARTIFACT_NAMES}
        return result

    def _project_get(self) -> None:
        if self.path == "/api/projects":
            self._json(200, {"projects": self.server.projects.list()})
            return
        match = re.fullmatch(rf"/api/projects/({PROJECT_ID})(?:/(builds)(?:/([0-9]{{6}})/(project\.[a-z]+|build\.log))?)?", self.path)
        if not match:
            raise FileNotFoundError("Unknown project endpoint")
        project_id, builds, number, filename = match.groups()
        self.server.projects.load(project_id)
        if not builds:
            self._json(200, self.server.projects.load(project_id))
        elif not number:
            self._json(200, {"builds": [self._build_summary(project_id, item) for item in self.server.project_builds.history(project_id)]})
        else:
            manifest = self.server.project_builds.load(project_id, number)
            if filename == "build.log":
                file = self.server.project_builds.directory(project_id, number) / filename
            elif filename in ARTIFACT_NAMES:
                file = self.server.project_builds.result(project_id, number).file(filename)
            else:
                raise FileNotFoundError("Unknown build artifact")
            suffix = file.suffix if filename != "build.log" else ".log"
            fallback = f"{project_id[:8]}-{number}{suffix}"
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", manifest["name"]).strip(". ")[:80] or "project"
            self._download(file, fallback, f"{name}-{fallback}")

    def _download(self, file: Path, filename: str, display_name: str) -> None:
        content = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(file.name))
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"; filename*=UTF-8\'\'{quote(display_name, safe="")}')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        if self.path.startswith("/api/projects"):
            try:
                with self.server.operation_lock:
                    self._project_get()
            except (ValueError, OSError, KeyError, TypeError) as exc:
                self._json(404, {"error": {"message": str(exc), "path": None}})
            return
        if not self.path.startswith("/api/artifacts/"):
            super().do_GET()
            return
        match = re.fullmatch(r"/api/artifacts/([0-9a-f]{32})/(project\.[a-z]+)", self.path)
        result = self.server.builds.get(match[1]) if match else None
        if not result or match[2] not in ARTIFACT_NAMES:
            self._json(404, {"error": {"message": "Unknown build artifact", "path": None}})
            return
        try:
            content = (result.directory / match[2]).read_bytes()
        except OSError:
            self._json(404, {"error": {"message": "Build artifact is no longer available", "path": None}})
            return
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(match[2]))
        self.send_header("Content-Disposition", f'attachment; filename="{match[2]}"')
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def create_editor_server(
    port: int = 8765, directory: Path = EDITOR_DIST, *,
    build_root: Path = EDITOR_BUILDS, assembler: str = "sjasmplus", emulator: str = "emuz",
    project_root: Path = PROJECTS_ROOT, project_build_root: Path | None = None,
) -> ThreadingHTTPServer:
    if not (directory / "index.html").is_file():
        raise ValueError("Editor is not built. Run 'npm ci' then 'npm run build' in editor/.")
    server = EditorHTTPServer(("127.0.0.1", port), partial(EditorHandler, directory=str(directory)))
    server.build_root = build_root.resolve()
    server.projects = ProjectStore(project_root)
    server.project_builds = BuildStore(project_build_root or build_root.parent / "projects")
    server.assembler = assembler
    server.emulator = emulator
    server.builds = {}
    server.emulator_processes = []
    server.operation_lock = threading.Lock()
    return server


def serve_editor(port: int = 8765, open_browser: bool = False) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("Editor port must be 1..65535")
    with create_editor_server(port) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"ZXBlocks editor: {url} (Ctrl+C to stop)", flush=True)
        if open_browser:
            import webbrowser
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
