"""Loopback-only editor host and compiler API; no third-party Python packages."""

from __future__ import annotations

import json
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .compiler import CompileError, compile_project

MAX_REQUEST_BYTES = 1024 * 1024
EDITOR_DIST = Path(__file__).resolve().parents[2] / "editor" / "dist"


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
        if self.path != "/api/compile":
            self._json(404, {"error": {"message": "Unknown endpoint", "path": None}})
            return
        origin = self.headers.get("Origin")
        allowed = {f"http://127.0.0.1:{self.server.server_port}",
                   f"http://localhost:{self.server.server_port}"}
        if origin and origin not in allowed:
            self._json(403, {"error": {"message": "Same-origin requests only", "path": None}})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                self._json(413, {"error": {"message": "Project must be 1 byte to 1 MiB", "path": None}})
                return
            project = json.loads(self.rfile.read(length).decode("utf-8"))
            asm = compile_project(project)
        except (CompileError, ValueError, UnicodeError, RecursionError) as exc:
            self._json(400, {"error": {"message": str(exc), "path": getattr(exc, "path", None)}})
            return
        self._json(200, {"asm": asm})


def create_editor_server(port: int = 8765, directory: Path = EDITOR_DIST) -> ThreadingHTTPServer:
    if not (directory / "index.html").is_file():
        raise ValueError("Editor is not built. Run 'npm ci' then 'npm run build' in editor/.")
    return EditorHTTPServer(("127.0.0.1", port), partial(EditorHandler, directory=str(directory)))


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
