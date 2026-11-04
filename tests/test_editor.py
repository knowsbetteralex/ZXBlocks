"""Compiler diagnostics and the editor's stdlib-only HTTP integration."""

import json
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zxblocks.compiler import CompileError, compile_project
from zxblocks.editor import MAX_REQUEST_BYTES, create_editor_server
from zxblocks.runner import ARTIFACT_NAMES, BuildError, BuildResult


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
        cls.server = create_editor_server(0, Path(cls.directory.name), build_root=Path(cls.directory.name) / "builds")
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
        self.assertEqual(self.request(b"{}", "/api/unknown")[0], 404)
        self.assertEqual(self.request(b"{}", headers={"Origin": "https://example.org"})[0], 403)

    def test_missing_bundle_has_actionable_message(self):
        with self.assertRaisesRegex(ValueError, "npm ci"):
            create_editor_server(0, Path(self.directory.name) / "missing")

    def test_second_editor_cannot_share_the_active_port(self):
        with self.assertRaises(OSError):
            duplicate = create_editor_server(self.server.server_port, Path(self.directory.name))
            duplicate.server_close()

    @staticmethod
    def fake_build(project, directory, assembler):
        directory.mkdir(parents=True)
        for name in ARTIFACT_NAMES:
            (directory / name).write_bytes(b"artifact")
        (directory / "project.json").write_text(json.dumps(project), encoding="utf-8")
        return BuildResult(directory, 72)

    def test_build_downloads_the_exact_submitted_project_in_a_new_directory(self):
        project = json.loads(EXAMPLE.read_text(encoding="utf-8"))
        with patch("zxblocks.editor.build_project", side_effect=self.fake_build):
            status, first = self.request(json.dumps(project).encode(), "/api/build")
            self.assertEqual(status, 200)
            self.assertFalse(first["launched"])
            project["variables"][0]["initial"] = 42
            status, second = self.request(json.dumps(project).encode(), "/api/build")
        self.assertNotEqual(first["artifacts"]["json"], second["artifacts"]["json"])
        for response, initial in ((first, 0), (second, 42)):
            with urlopen(self.url + response["artifacts"]["json"], timeout=5) as download:
                self.assertIn('attachment; filename="project.json"', download.headers["Content-Disposition"])
                self.assertEqual(json.load(download)["variables"][0]["initial"], initial)

    def test_run_builds_then_launches_current_snapshot_once(self):
        order = []
        def build(project, directory, assembler):
            order.append("build")
            return self.fake_build(project, directory, assembler)
        def launch(result, emulator):
            order.append("launch")
            self.assertTrue(result.snapshot.is_file())
            return Mock(pid=1234, poll=Mock(return_value=0))
        project = {"format": "zxblocks/v2", "name": "Current unsaved project"}
        with patch("zxblocks.editor.require_tool"), \
             patch("zxblocks.editor.build_project", side_effect=build), \
             patch("zxblocks.editor.launch_emulator", side_effect=launch) as launcher:
            status, body = self.request(json.dumps(project).encode(), "/api/run")
        self.assertEqual(status, 200)
        self.assertTrue(body["launched"])
        self.assertEqual(order, ["build", "launch"])
        launcher.assert_called_once()

    def test_missing_emulator_and_bad_ir_never_launch_or_build(self):
        with patch("zxblocks.editor.require_tool", side_effect=BuildError("emuz not in PATH")), \
             patch("zxblocks.editor.build_project") as build, patch("zxblocks.editor.launch_emulator") as launch:
            self.assertEqual(self.request(b'{"format":"zxblocks/v1"}', "/api/run")[0], 400)
            self.assertEqual(self.request(b'{"format":"unknown"}', "/api/run")[0], 400)
        build.assert_not_called()
        launch.assert_not_called()

    def test_failed_build_never_launches_a_stale_artifact(self):
        with patch("zxblocks.editor.require_tool"), \
             patch("zxblocks.editor.build_project", side_effect=BuildError("assembly failed")), \
             patch("zxblocks.editor.launch_emulator") as launch:
            status, body = self.request(b'{"format":"zxblocks/v1"}', "/api/run")
        self.assertEqual(status, 400)
        self.assertIn("assembly failed", body["error"]["message"])
        launch.assert_not_called()

    def test_run_and_build_reject_cross_origin_before_invoking_tools(self):
        with patch("zxblocks.editor.build_project") as build, patch("zxblocks.editor.launch_emulator") as launch:
            for endpoint in ("/api/build", "/api/run"):
                self.assertEqual(self.request(b"{}", endpoint, {"Origin": "https://example.org"})[0], 403)
        build.assert_not_called()
        launch.assert_not_called()

    def test_artifacts_cannot_expose_arbitrary_files_or_packaging_source(self):
        with patch("zxblocks.editor.build_project", side_effect=self.fake_build):
            _, result = self.request(b'{"format":"zxblocks/v1"}', "/api/build")
        prefix = result["artifacts"]["json"].rsplit("/", 1)[0]
        for path in (prefix + "/_snapshot.asm", prefix + "/../index.html", prefix + "/project.exe",
                     "/api/artifacts/" + "0" * 32 + "/project.json"):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.url + path, timeout=5)
            self.assertEqual(caught.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
