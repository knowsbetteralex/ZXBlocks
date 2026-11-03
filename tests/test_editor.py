"""Compiler diagnostics and the editor's stdlib-only HTTP integration."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zxblocks.compiler import CompileError, compile_project
from zxblocks.editor import MAX_REQUEST_BYTES, create_editor_server


EXAMPLE = Path(__file__).resolve().parents[1] / "examples/border_cycle/project.json"


class DiagnosticTests(unittest.TestCase):
    def test_nested_error_reports_innermost_action_path(self):
        project = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        project["events"]["frame"][1]["then"][0]["var"] = "missing"
        with self.assertRaises(CompileError) as caught:
            compile_project(project)
        self.assertEqual(caught.exception.path, "events.frame[1].then[0]")

    def test_malformed_comparison_is_a_diagnostic_not_a_type_error(self):
        for value in ([], {}, None, 42):
            with self.subTest(value=value):
                project = json.loads(EXAMPLE.read_text(encoding="utf-8"))
                project["events"]["frame"][1]["condition"]["op"] = value
                with self.assertRaises(CompileError) as caught:
                    compile_project(project)
                self.assertEqual(caught.exception.path, "events.frame[1]")


class EditorServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        Path(cls.directory.name, "index.html").write_text("editor fixture", encoding="utf-8")
        cls.server = create_editor_server(0, Path(cls.directory.name))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()
        cls.directory.cleanup()

    def request(self, body, path="/api/compile", headers=None):
        request = Request(self.url + path, data=body, headers=headers or {"Content-Type": "application/json"})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_serves_static_editor(self):
        with urlopen(self.url, timeout=5) as response:
            self.assertEqual(response.read(), b"editor fixture")

    def test_compiles_identical_assembly(self):
        project = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        status, body = self.request(json.dumps(project).encode())
        self.assertEqual(status, 200)
        self.assertEqual(body["asm"], compile_project(project))

    def test_structured_diagnostic(self):
        project = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        project["events"]["frame"][0]["var"] = "missing"
        status, body = self.request(json.dumps(project).encode())
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["path"], "events.frame[0]")
        self.assertIn("Unknown variable", body["error"]["message"])

    def test_v2_keyboard_uses_the_same_compiler_endpoint(self):
        project = json.loads((EXAMPLE.parent.parent / "keyboard_border/project.json").read_text(encoding="utf-8"))
        status, body = self.request(json.dumps(project).encode())
        self.assertEqual(status, 200)
        self.assertEqual(body["asm"], compile_project(project))
        self.assertIn("IN A,(C)", body["asm"])

    def test_rejects_bad_json_and_excessive_body(self):
        self.assertEqual(self.request(b"{")[0], 400)
        self.assertEqual(self.request(b" " * (MAX_REQUEST_BYTES + 1))[0], 413)

    def test_rejects_unknown_endpoint_and_cross_origin(self):
        self.assertEqual(self.request(b"{}", "/api/build")[0], 404)
        self.assertEqual(self.request(b"{}", headers={"Origin": "https://example.org"})[0], 403)

    def test_missing_bundle_has_actionable_message(self):
        with self.assertRaisesRegex(ValueError, "npm ci"):
            create_editor_server(0, Path(self.directory.name) / "missing")

    def test_second_editor_cannot_share_the_active_port(self):
        with self.assertRaises(OSError):
            duplicate = create_editor_server(self.server.server_port, Path(self.directory.name))
            duplicate.server_close()


if __name__ == "__main__":
    unittest.main()
