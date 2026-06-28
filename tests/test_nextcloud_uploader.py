import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "nextcloud_uploader.py"
SPEC = importlib.util.spec_from_file_location("nextcloud_uploader", MODULE_PATH)
nextcloud_uploader = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(nextcloud_uploader)


class FakeResponse:
    def __init__(self, status_code=201, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.calls = []
        self.auth = None

    def request(self, method, url, timeout):
        self.calls.append((method, url, timeout))
        return FakeResponse(201)

    def put(self, url, data, headers, timeout):
        self.calls.append(("PUT", url, data.read(), headers, timeout))
        return FakeResponse(201)

    def post(self, url, headers, data, timeout):
        self.calls.append(("POST", url, headers, data, timeout))
        return FakeResponse(200, payload={"ocs": {"data": {"url": "https://nextcloud/s/share"}}})


def test_remote_path_to_webdav_url_encodes_unicode(monkeypatch):
    monkeypatch.setattr(nextcloud_uploader, "NEXTCLOUD_URL", "https://nextcloud.example")
    monkeypatch.setattr(nextcloud_uploader, "NEXTCLOUD_DAV_USER", "user@example.com")

    url = nextcloud_uploader.remote_path_to_webdav_url("/Documents/Recipe/Десерти/Кекс.docx")

    assert url.startswith("https://nextcloud.example/remote.php/dav/files/user%40example.com/")
    assert "%D0%94%D0%B5%D1%81%D0%B5%D1%80%D1%82%D0%B8" in url


def test_ensure_remote_folders_creates_each_level(monkeypatch):
    monkeypatch.setattr(nextcloud_uploader, "NEXTCLOUD_URL", "https://nextcloud.example")
    monkeypatch.setattr(nextcloud_uploader, "NEXTCLOUD_DAV_USER", "user")
    session = FakeSession()

    nextcloud_uploader.ensure_remote_folders(session, "/Documents/Recipe/Інше")

    methods = [call[0] for call in session.calls]
    assert methods == ["MKCOL", "MKCOL", "MKCOL"]


def test_upload_file_uses_put(monkeypatch, tmp_path):
    monkeypatch.setattr(nextcloud_uploader, "NEXTCLOUD_URL", "https://nextcloud.example")
    monkeypatch.setattr(nextcloud_uploader, "NEXTCLOUD_DAV_USER", "user")
    local_path = tmp_path / "recipe.pdf"
    local_path.write_bytes(b"%PDF")
    session = FakeSession()

    url = nextcloud_uploader.upload_file(session, local_path, "/Documents/Recipe/recipe.pdf")

    assert url.endswith("/Documents/Recipe/recipe.pdf")
    assert session.calls[0][0] == "PUT"
    assert session.calls[0][2] == b"%PDF"


def test_create_share_link_returns_empty_on_failure(monkeypatch):
    class FailingSession(FakeSession):
        def post(self, url, headers, data, timeout):
            return FakeResponse(500, text="error")

    monkeypatch.setattr(nextcloud_uploader, "NEXTCLOUD_CREATE_SHARES", True)

    assert nextcloud_uploader.create_share_link(FailingSession(), "/Documents/Recipe/a.pdf") == ""
