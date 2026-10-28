import hashlib
import importlib.util
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "data" / "scripts" / "download_ud_latin.py"
spec = importlib.util.spec_from_file_location("download_ud_latin", SCRIPT)
assert spec and spec.loader
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)

BODY_A = b"# sent_id = a1\n1\tarma\tarma\tNOUN\t_\t_\t0\troot\t_\t_\n\n"
BODY_B = b"# sent_id = b1\n1\tvirum\tvir\tNOUN\t_\t_\t0\troot\t_\t_\n\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def server(tmp_path: Path):
    """Serve files laid out like raw.githubusercontent.com: /<repo>/<release>/<name>."""
    site = tmp_path / "site"
    (site / "UD_Latin-Test" / "r0.0").mkdir(parents=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    httpd = HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_port}/{{repo}}/{{release}}/{{name}}"
    yield site / "UD_Latin-Test" / "r0.0", base
    httpd.shutdown()


@pytest.fixture
def files(monkeypatch):
    manifest = (
        dl.UDFile("UD_Latin-Test", "la_a-ud-test.conllu", sha(BODY_A), len(BODY_A)),
        dl.UDFile("UD_Latin-Test", "la_b-ud-train.conllu", sha(BODY_B), len(BODY_B)),
    )
    monkeypatch.setattr(dl, "FILES", manifest)
    monkeypatch.setattr(dl, "RELEASE", "r0.0")
    return manifest


def run(base: str, dest_dir: Path, *extra: str) -> int:
    return dl.main(["--base-url", base, "--dest-dir", str(dest_dir), *extra])


def test_pinned_release_and_manifest_cover_adr_003():
    assert dl.RELEASE == "r2.18"
    names = {f.name for f in dl.FILES}
    # test splits of the parse-set treebanks
    for tb in ("perseus", "proiel", "ittb"):
        assert f"la_{tb}-ud-test.conllu" in names
    # train splits of all six, for frequency bands
    for tb in ("perseus", "proiel", "ittb", "llct", "udante", "circse"):
        assert f"la_{tb}-ud-train.conllu" in names
    assert all(len(f.sha256) == 64 and f.size > 0 for f in dl.FILES)


def test_default_dest_is_raw_ud():
    assert SCRIPT.parents[1] / "raw" / "ud" == dl.DEST_DIR


def test_downloads_all_files_then_skips(tmp_path: Path, server, files, capsys):
    site, base = server
    (site / "la_a-ud-test.conllu").write_bytes(BODY_A)
    (site / "la_b-ud-train.conllu").write_bytes(BODY_B)
    dest_dir = tmp_path / "raw" / "ud"

    assert run(base, dest_dir) == 0
    assert (dest_dir / "la_a-ud-test.conllu").read_bytes() == BODY_A
    assert (dest_dir / "la_b-ud-train.conllu").read_bytes() == BODY_B

    (site / "la_a-ud-test.conllu").unlink()  # a second run must not touch the network
    (site / "la_b-ud-train.conllu").unlink()
    capsys.readouterr()
    assert run(base, dest_dir) == 0
    assert capsys.readouterr().out.count("skipping") == 2


def test_wrong_checksum_leaves_no_file(tmp_path: Path, server, files):
    site, base = server
    (site / "la_a-ud-test.conllu").write_bytes(BODY_A.replace(b"arma", b"armo"))
    (site / "la_b-ud-train.conllu").write_bytes(BODY_B)
    dest_dir = tmp_path / "raw" / "ud"

    assert run(base, dest_dir) == 1
    assert not (dest_dir / "la_a-ud-test.conllu").exists()
    assert not list(dest_dir.glob("*.part"))


def test_corrupt_existing_file_is_redownloaded(tmp_path: Path, server, files):
    site, base = server
    (site / "la_a-ud-test.conllu").write_bytes(BODY_A)
    (site / "la_b-ud-train.conllu").write_bytes(BODY_B)
    dest_dir = tmp_path / "raw" / "ud"
    dest_dir.mkdir(parents=True)
    (dest_dir / "la_a-ud-test.conllu").write_bytes(BODY_A[:10])

    assert run(base, dest_dir) == 0
    assert (dest_dir / "la_a-ud-test.conllu").read_bytes() == BODY_A


def test_force_redownloads_valid_file(tmp_path: Path, server, files, capsys):
    site, base = server
    (site / "la_a-ud-test.conllu").write_bytes(BODY_A)
    (site / "la_b-ud-train.conllu").write_bytes(BODY_B)
    dest_dir = tmp_path / "raw" / "ud"
    assert run(base, dest_dir) == 0

    capsys.readouterr()
    assert run(base, dest_dir, "--force") == 0
    assert "skipping" not in capsys.readouterr().out


def test_missing_remote_file_fails(tmp_path: Path, server, files):
    site, base = server
    (site / "la_b-ud-train.conllu").write_bytes(BODY_B)  # la_a is not served
    dest_dir = tmp_path / "raw" / "ud"

    assert run(base, dest_dir) == 1
    assert not (dest_dir / "la_a-ud-test.conllu").exists()
