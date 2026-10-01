"""Save project to file / Open project from file, integrity checks, and the
permanent session cookie."""
import io
import json
import logging
import tempfile
import unittest
from unittest import mock

import app as flaskapp
from eudoxa import EudoxaManager, VDiff, BT, TRUE

logging.getLogger("eudoxa").setLevel(logging.WARNING)


def sample_mgr():
    mgr = EudoxaManager()
    mgr.add_aspect("Betyg", "str")
    for level in ["VG", "G", "IG"]:
        mgr.add_aspect_level("Betyg", level, None)
    mgr.add_aspect("Kostnad", "int")
    for level in ["0", "800"]:
        mgr.add_aspect_level("Kostnad", level, None)
    mgr.try_set_aspect_level_relation("Betyg", "VG", "G", BT)
    mgr.add_consequence("c1", {"Betyg": "VG", "Kostnad": "800"})
    return mgr


class ProjectFileTestCase(unittest.TestCase):
    """Flask test client with the project store in a temporary directory."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.object(flaskapp, "_STORE_DIR", tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = flaskapp.app.test_client()

    def create_project(self, name="Konsert – test", author="Anna", client=None):
        """Create a project in the client's session and store sample_mgr() in it."""
        client = client or self.client
        res = client.post("/api/project", json={"project_name": name, "author": author})
        self.assertEqual(res.status_code, 201)
        with client.session_transaction() as sess:
            sid = sess["sid"]
        with flaskapp.app.test_request_context():
            from flask import session
            session.update({"sid": sid, "project_name": name, "author": author})
            flaskapp.save_manager(sample_mgr())
        return sid

    def open_file(self, content, filename="project.eudoxa.json"):
        if not isinstance(content, bytes):
            content = json.dumps(content).encode("utf-8")
        return self.client.post("/api/project/open", data={"file": (io.BytesIO(content), filename)},
                                content_type="multipart/form-data")


class TestDownload(ProjectFileTestCase):

    def test_download_wraps_project_with_metadata(self):
        self.create_project()
        res = self.client.get("/api/project/download")
        self.assertEqual(res.status_code, 200)
        self.assertIn("attachment", res.headers["Content-Disposition"])
        self.assertIn(".eudoxa.json", res.headers["Content-Disposition"])
        data = json.loads(res.data.decode("utf-8"))
        self.assertEqual(data["format"], flaskapp.PROJECT_FILE_FORMAT)
        self.assertEqual(data["format_version"], flaskapp.PROJECT_FILE_VERSION)
        self.assertEqual(data["project_name"], "Konsert – test")
        self.assertEqual(data["author"], "Anna")
        self.assertIn("build", data)
        self.assertIn("exported_at", data)
        self.assertEqual(data["project"], sample_mgr().to_dict())

    def test_download_without_project_is_400(self):
        self.assertEqual(self.client.get("/api/project/download").status_code, 400)

    def test_safe_filename(self):
        self.assertEqual(flaskapp._safe_filename('a/b:c*?"<>|'), "a_b_c______")
        self.assertEqual(flaskapp._safe_filename("  "), "project")
        self.assertEqual(flaskapp._safe_filename("Bostäder"), "Bostäder")


class TestOpen(ProjectFileTestCase):

    def downloaded(self):
        """A file as produced by 'Save project to file' in another browser."""
        other = flaskapp.app.test_client()
        self.create_project(client=other)
        return other.get("/api/project/download").data

    def test_round_trip(self):
        res = self.open_file(self.downloaded())
        self.assertEqual(res.status_code, 201, res.get_json())
        self.assertEqual(self.client.get("/api/project").get_json(),
                         {"project_name": "Konsert – test", "author": "Anna"})
        # The stored project is identical to the one that was saved.
        res = self.client.get("/api/project/download")
        self.assertEqual(json.loads(res.data)["project"], sample_mgr().to_dict())

    def test_raw_store_file_opens_with_name_from_file(self):
        raw = sample_mgr().to_dict()
        res = self.open_file(raw, filename="Deponi.json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.get_json()["project_name"], "Deponi")

    def test_refused_while_a_project_is_open(self):
        self.create_project()
        res = self.open_file(self.downloaded())
        self.assertEqual(res.status_code, 409)

    def test_allowed_after_delete(self):
        self.create_project()
        self.client.delete("/api/project")
        self.assertEqual(self.open_file(self.downloaded()).status_code, 201)

    def test_not_json(self):
        res = self.open_file(b"PK\x03\x04 this is an xlsx", filename="x.xlsx")
        self.assertEqual(res.status_code, 400)
        self.assertIn("not an Eudoxa project file", res.get_json()["error"])

    def test_json_but_not_a_project(self):
        self.assertEqual(self.open_file({"hello": "world"}).status_code, 400)
        self.assertEqual(self.open_file([1, 2, 3]).status_code, 400)

    def test_newer_format_version_refused(self):
        data = json.loads(self.downloaded())
        data["format_version"] = flaskapp.PROJECT_FILE_VERSION + 1
        res = self.open_file(data)
        self.assertEqual(res.status_code, 400)
        self.assertIn("newer version", res.get_json()["error"])

    def test_inconsistent_file_refused_with_problems(self):
        data = json.loads(self.downloaded())
        data["project"]["consequences"]["c1"]["aspect_levels"]["Betyg"] = "MVG"
        res = self.open_file(data)
        self.assertEqual(res.status_code, 400)
        self.assertTrue(any("MVG" in p for p in res.get_json()["problems"]))
        # Nothing was opened.
        self.assertEqual(self.client.get("/api/project").status_code, 404)

    def test_too_large(self):
        with mock.patch.object(flaskapp, "MAX_PROJECT_FILE_BYTES", 100):
            res = self.open_file(self.downloaded())
        self.assertEqual(res.status_code, 413)


class TestStoreFileAndSession(ProjectFileTestCase):

    def test_store_file_holds_name_and_author_and_follows_rename(self):
        sid = self.create_project()
        self.client.put("/api/project", json={"project_name": "Nytt namn", "author": ""})
        with open(flaskapp._store_path(sid), encoding="utf-8") as f:
            stored = json.load(f)
        self.assertEqual(stored["project_name"], "Nytt namn")
        self.assertEqual(stored["author"], "")
        # The extra keys don't disturb loading.
        EudoxaManager.from_dict(stored)

    def test_session_cookie_is_persistent(self):
        res = self.client.post("/api/project", json={"project_name": "P"})
        cookie = res.headers.get("Set-Cookie", "")
        self.assertIn("Expires=", cookie)

    def test_old_non_permanent_session_is_upgraded(self):
        with self.client.session_transaction() as sess:
            sess["sid"] = "abc123"      # as issued before sessions were permanent
        res = self.client.get("/api/project")
        self.assertIn("Expires=", res.headers.get("Set-Cookie", ""))


class TestIntegrityProblems(unittest.TestCase):

    def test_sound_manager_has_no_problems(self):
        self.assertEqual(sample_mgr().integrity_problems(), [])
        self.assertEqual(EudoxaManager().integrity_problems(), [])

    def test_missing_vdcm_row_and_bad_value(self):
        mgr = sample_mgr()
        del mgr.vdiff_comparison_matrix[VDiff("Betyg", "VG", "IG")]
        problems = mgr.integrity_problems()
        self.assertTrue(any("lacks" in p for p in problems))
        self.assertTrue(any("incomplete" in p for p in problems))

        mgr = sample_mgr()
        row = mgr.vdiff_comparison_matrix[VDiff("Betyg", "VG", "G")]
        row[VDiff("Betyg", "G", "IG")] = "maybe"
        self.assertTrue(any("invalid values" in p for p in mgr.integrity_problems()))

    def test_unknown_consequence_aspect(self):
        mgr = sample_mgr()
        mgr.consequences["c1"].aspect_levels["Pris"] = "10"
        self.assertTrue(any("unknown aspect 'Pris'" in p for p in mgr.integrity_problems()))


if __name__ == "__main__":
    unittest.main()
