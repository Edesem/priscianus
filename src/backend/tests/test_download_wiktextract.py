import importlib.util
import json
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "data" / "scripts" / "download_wiktextract.py"
spec = importlib.util.spec_from_file_location("download_wiktextract", SCRIPT)
assert spec and spec.loader
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)

GOOD = b'{"word": "amo"}\n{"word": "rosa"}\n'


@pytest.fixture
def server(tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()
    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield site, f"http://127.0.0.1:{httpd.server_port}/dump.jsonl"
    httpd.shutdown()


def test_is_complete(tmp_path: Path):
    f = tmp_path / "x.jsonl"
    f.write_bytes(GOOD)
    assert dl.is_complete(f)
    f.write_bytes(GOOD + b'{"word": "tru')
    assert not dl.is_complete(f)
    f.write_bytes(b"")
    assert not dl.is_complete(f)


def test_downloads_then_skips(tmp_path: Path, server, capsys):
    site, url = server
    (site / "dump.jsonl").write_bytes(GOOD)
    dest_dir = tmp_path / "raw"

    assert dl.main(["--url", url, "--dest-dir", str(dest_dir)]) == 0
    dest = dest_dir / dl.FILENAME
    assert dest.read_bytes() == GOOD
    assert json.loads((dest_dir / (dl.FILENAME + ".meta.json")).read_text())["bytes"] == len(GOOD)

    (site / "dump.jsonl").unlink()  # a second run must not touch the network
    assert dl.main(["--url", url, "--dest-dir", str(dest_dir)]) == 0
    assert "skipping" in capsys.readouterr().out
    assert dest.read_bytes() == GOOD


def test_truncated_existing_file_is_redownloaded(tmp_path: Path, server):
    site, url = server
    (site / "dump.jsonl").write_bytes(GOOD)
    dest_dir = tmp_path / "raw"
    dest_dir.mkdir()
    (dest_dir / dl.FILENAME).write_bytes(b'{"word": "am')

    assert dl.main(["--url", url, "--dest-dir", str(dest_dir)]) == 0
    assert (dest_dir / dl.FILENAME).read_bytes() == GOOD


def test_bad_download_leaves_no_file(tmp_path: Path, server):
    site, url = server
    (site / "dump.jsonl").write_bytes(b'{"word": "tru')
    dest_dir = tmp_path / "raw"

    assert dl.main(["--url", url, "--dest-dir", str(dest_dir)]) == 1
    assert list(dest_dir.iterdir()) == []
