"""Managed drafts, project switching, persistent build history and safe reuse."""

import copy
import json
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from zxblocks.build_store import BuildStore
from zxblocks.editor import create_editor_server
from zxblocks.project_store import ProjectStore, RevisionConflict
from zxblocks.runner import ARTIFACT_NAMES, BuildError, BuildResult

ROOT = Path(__file__).resolve().parents[1]
IR = json.loads((ROOT / "examples/border_cycle/project.json").read_text(encoding="utf-8"))


def document(name="Project A", valid=True):
    project = copy.deepcopy(IR)
    project["name"] = name
    return {"format": "zxblocks/editor/v2", "metadata": {"name": name, "format": "zxblocks/v1", "initials": {}},
            "workspace": {}, "view": {"scale": 0.8, "scrollX": 10, "scrollY": -20}, "project": project if valid else None}


def fake_build(project, directory, assembler):
    directory.mkdir(parents=True)
    for name in ARTIFACT_NAMES:
        (directory / name).write_bytes(b"artifact")
    (directory / "project.json").write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
    return BuildResult(directory, 52)


class ProjectStoreTests(unittest.TestCase):
    def test_saved_projects_and_unfinished_drafts_survive_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory))
            first = store.create(document())
            second = store.create(document("Project B"))
            draft = document(valid=False)
            draft["workspace"] = {"blocks": {"languageVersion": 0, "blocks": [{"type": "zxb_byte", "id": "detached", "x": 450, "y": 55}]}}
            store.save(first["id"], draft, first["revision"])
            reopened = ProjectStore(Path(directory))
            self.assertEqual(reopened.load(first["id"])["document"], draft)
            self.assertEqual(reopened.load(second["id"])["document"], second["document"])
            self.assertFalse((store.directory(first["id"]) / "project.json").exists())
            self.assertEqual(len(reopened.list()), 2)

    def test_conflicting_revision_never_overwrites_saved_work(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory))
            first = store.create(document())
            current = store.save(first["id"], document("Renamed"), 1)
            with self.assertRaises(RevisionConflict):
                store.save(first["id"], document("Stale tab"), 1)
            self.assertEqual(store.load(first["id"]), current)
            self.assertEqual(json.loads((store.directory(first["id"]) / "project.json").read_text(encoding="utf-8"))["name"], "Renamed")

    def test_invalid_document_or_path_does_not_create_a_project(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ProjectStore(Path(directory) / "projects")
            for invalid in (None, {}, {**document(), "format": "zxblocks/editor/v99"}, {**document(), "executable": "anything"}):
                with self.assertRaises(ValueError):
                    store.create(invalid)
            with self.assertRaises(ValueError):
                store.load("../escape")
            self.assertFalse(store.root.exists())


class BuildReuseTests(unittest.TestCase):
    def test_compiler_or_assembler_changes_invalidate_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "assembler"
            executable.write_bytes(b"assembler v1")
            store = BuildStore(root / "builds")
            project_id = "a" * 32
            with patch("zxblocks.build_store.require_tool", return_value=str(executable)), \
                 patch("zxblocks.build_store.build_project", side_effect=fake_build) as build:
                first, _, reused = store.build(project_id, IR, "assembler")
                self.assertFalse(reused)
                self.assertTrue(store.build(project_id, IR, "assembler")[2])
                with patch("zxblocks.build_store.COMPILER_FINGERPRINT", "compiler v2"):
                    second, _, reused = store.build(project_id, IR, "assembler")
                    self.assertFalse(reused)
                    executable.write_bytes(b"assembler v2")
                    third, _, reused = store.build(project_id, IR, "assembler")
                    self.assertFalse(reused)
                self.assertEqual(build.call_count, 3)
            self.assertEqual([first["number"], second["number"], third["number"]], ["000001", "000002", "000003"])


class ManagedEditorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "index.html").write_text("fixture", encoding="utf-8")
        self.server = create_editor_server(0, self.root, project_root=self.root / "sources",
            build_root=self.root / "legacy", project_build_root=self.root / "builds")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown(); self.thread.join(timeout=5); self.server.server_close()
        self.temporary.cleanup()

    def request(self, path, body=None, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        request = Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def create(self, name="Project A"):
        status, record = self.request("/api/projects", {"document": document(name)})
        self.assertEqual(status, 200)
        return record

    def test_project_list_save_conflict_and_same_origin(self):
        record = self.create()
        prefix = f"/api/projects/{record['id']}"
        self.assertEqual(self.request(prefix)[1], record)
        self.assertEqual(self.request(prefix + "/save", {"revision": 1, "document": document("Changed")})[0], 200)
        self.assertEqual(self.request(prefix + "/save", {"revision": 1, "document": document("Stale")})[0], 409)
        self.assertEqual(self.request("/api/projects")[1]["projects"][0]["name"], "Changed")
        with patch("zxblocks.editor.launch_emulator") as launch:
            for path in ("/api/projects", prefix + "/save", prefix + "/run", prefix + "/build", prefix + "/builds/000001/run"):
                self.assertEqual(self.request(path, {}, origin="https://example.org")[0], 403)
        launch.assert_not_called()

    def test_v3_document_and_draft_are_saved_and_build_the_exact_expression_ir(self):
        project = json.loads((ROOT / "examples/arithmetic_border/project.json").read_text(encoding="utf-8"))
        state = document(project["name"])
        state["metadata"]["format"] = "zxblocks/v3"
        state["project"] = project
        status, record = self.request("/api/projects", {"document": state})
        self.assertEqual(status, 200)
        prefix = f"/api/projects/{record['id']}"
        with patch("zxblocks.build_store.require_tool", return_value=sys.executable), \
             patch("zxblocks.build_store.build_project", side_effect=fake_build):
            status, built = self.request(prefix + "/build", {"project": project})
        self.assertEqual(status, 200)
        with urlopen(self.url + built["build"]["artifacts"]["json"], timeout=5) as response:
            self.assertEqual(json.load(response), project)
        state["project"] = None
        status, saved = self.request(prefix + "/save", {"revision": record["revision"], "document": state})
        self.assertEqual(status, 200)
        self.assertEqual(self.request(prefix)[1]["document"]["metadata"]["format"], "zxblocks/v3")
        self.assertIsNone(saved["document"]["project"])

    def test_builds_belong_to_selected_project_and_persist_with_classified_files(self):
        first = self.create()
        second = self.create("Project B")
        prefix = f"/api/projects/{first['id']}"
        project = first["document"]["project"]
        with patch("zxblocks.build_store.require_tool", return_value=sys.executable), \
             patch("zxblocks.build_store.build_project", side_effect=fake_build) as build:
            status, body = self.request(prefix + "/build", {"project": project})
            self.assertEqual(status, 200)
            _, repeat = self.request(prefix + "/build", {"project": project})
            self.assertTrue(repeat["reused"])
            self.assertEqual(build.call_count, 1)
            _, other = self.request(f"/api/projects/{second['id']}/build", {"project": second["document"]["project"]})
        self.assertEqual(body["build"]["number"], other["build"]["number"])
        self.assertNotEqual(body["build"]["artifacts"]["sna"], other["build"]["artifacts"]["sna"])
        restarted = BuildStore(self.root / "builds")
        self.assertEqual(len(restarted.history(first["id"])), 1)
        result = restarted.result(first["id"], "000001")
        self.assertTrue(result.snapshot.is_file())
        self.assertEqual(result.snapshot.parent.name, "artifacts")
        self.assertEqual(result.file("project.asm").parent.name, "debug")
        self.assertEqual(result.file("project.json").parent.name, "source")
        self.assertEqual(json.loads((result.directory.parent / "latest.json").read_text())["number"], "000001")
        with urlopen(self.url + body["build"]["artifacts"]["json"], timeout=5) as response:
            self.assertEqual(json.load(response), project)
            self.assertIn(first["id"][:8] + "-000001.json", response.headers["Content-Disposition"])
        self.assertEqual(len(self.request(prefix + "/builds")[1]["builds"]), 1)

    def test_changed_source_or_missing_artifact_rebuilds_without_overwriting_history(self):
        record = self.create()
        prefix = f"/api/projects/{record['id']}"
        project = record["document"]["project"]
        with patch("zxblocks.build_store.require_tool", return_value=sys.executable), \
             patch("zxblocks.build_store.build_project", side_effect=fake_build):
            self.request(prefix + "/build", {"project": project})
            project["variables"][0]["initial"] = 42
            _, second = self.request(prefix + "/build", {"project": project})
            self.server.project_builds.result(record["id"], "000002").snapshot.unlink()
            _, third = self.request(prefix + "/build", {"project": project})
        self.assertEqual(second["build"]["number"], "000002")
        self.assertEqual(third["build"]["number"], "000003")
        first = self.server.project_builds.result(record["id"], "000001")
        self.assertEqual(json.loads(first.file("project.json").read_text())["variables"][0]["initial"], 0)

    def test_failed_build_and_invalid_program_never_launch_previous_success(self):
        record = self.create()
        prefix = f"/api/projects/{record['id']}"
        project = record["document"]["project"]
        with patch("zxblocks.build_store.require_tool", return_value=sys.executable), \
             patch("zxblocks.build_store.build_project", side_effect=fake_build):
            self.request(prefix + "/build", {"project": project})
        project["variables"][0]["initial"] = 5
        with patch("zxblocks.editor.require_tool"), patch("zxblocks.editor.launch_emulator") as launch, \
             patch("zxblocks.build_store.require_tool", return_value=sys.executable), \
             patch("zxblocks.build_store.build_project", side_effect=BuildError("Cannot assemble")):
            self.assertEqual(self.request(prefix + "/run", {"project": project})[0], 400)
            self.assertEqual(self.request(prefix + "/run", {"project": {"format": "wrong"}})[0], 400)
        launch.assert_not_called()
        history = self.request(prefix + "/builds")[1]["builds"]
        self.assertEqual(history[0]["status"], "failed")
        self.assertNotIn("artifacts", history[0])
        with urlopen(self.url + history[0]["log"], timeout=5) as response:
            self.assertIn(b"Cannot assemble", response.read())

    def test_only_explicit_history_action_launches_an_older_snapshot(self):
        record = self.create()
        prefix = f"/api/projects/{record['id']}"
        with patch("zxblocks.build_store.require_tool", return_value=sys.executable), \
             patch("zxblocks.build_store.build_project", side_effect=fake_build):
            self.request(prefix + "/build", {"project": record["document"]["project"]})
        with patch("zxblocks.editor.require_tool"), \
             patch("zxblocks.editor.launch_emulator", return_value=Mock(poll=Mock(return_value=0))) as launch:
            status, body = self.request(prefix + "/builds/000001/run", {})
        self.assertEqual(status, 200)
        self.assertTrue(body["launched"])
        self.assertEqual(launch.call_args.args[0].snapshot.parent.name, "artifacts")
        for path in (prefix + "/builds/000001/_snapshot.asm", prefix + "/builds/000001/../workspace.json",
                     prefix + "/workspace.json", "/api/projects/../sources", prefix + "/builds/000001/project.exe"):
            self.assertEqual(self.request(path)[0], 404)


@unittest.skipUnless(shutil.which("sjasmplus"), "Requires sjasmplus")
class OrganizedNativeBuildTests(unittest.TestCase):
    def test_real_assembly_and_source_mapping_survive_classification_and_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = BuildStore(Path(temporary))
            project_id = "a" * 32
            manifest, result, reused = store.build(project_id, IR, "sjasmplus")
            self.assertFalse(reused)
            self.assertEqual(result.code_size, 52)
            self.assertEqual(len(result.snapshot.read_bytes()), 49179)
            debug = result.directory / "debug"
            self.assertTrue((debug / "project.asm").is_file())
            self.assertIn("project.asm", result.file("project.sld").read_text(encoding="utf-8"))
            self.assertTrue((result.directory / "build.log").is_file())
            restarted = BuildStore(Path(temporary))
            repeated, existing, reused = restarted.build(project_id, IR, "sjasmplus")
            self.assertTrue(reused)
            self.assertEqual(manifest, repeated)
            self.assertEqual(result.snapshot, existing.snapshot)
