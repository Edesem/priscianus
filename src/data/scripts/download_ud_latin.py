"""Download the UD Latin treebank files used by the evals into src/data/raw/ud/.

Idempotent: files that are already present and match their pinned SHA-256 are
skipped. Standard library only, so it runs without installing the backend.

Files come from the `r2.18` tags of the UniversalDependencies/UD_Latin-*
repositories (see ADR-003): the test splits of Perseus, PROIEL and ITTB for the
parse set, and the train splits of all six treebanks for frequency bands. UD
tags do not change, so size and checksum are pinned. A download that does not
match is discarded.

Perseus, PROIEL and ITTB are CC BY-NC-SA: never commit the files (see
DATA_LICENCES.md).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import NamedTuple

RELEASE = "r2.18"
BASE_URL = (
    "https://raw.githubusercontent.com/UniversalDependencies/{repo}/{release}/{name}"
)
DEST_DIR = Path(__file__).resolve().parents[1] / "raw" / "ud"
CHUNK = 1 << 20


class UDFile(NamedTuple):
    repo: str
    name: str
    sha256: str
    size: int


FILES: tuple[UDFile, ...] = (
    UDFile(
        "UD_Latin-Perseus",
        "la_perseus-ud-test.conllu",
        "e0e53fdcc8040a2a6d3b6e7b5dfa69fa35d355ce11cae0682b61e6848745d386",
        1153778,
    ),
    UDFile(
        "UD_Latin-Perseus",
        "la_perseus-ud-train.conllu",
        "49d2e3813fc34595fe8cf569f263df4396e4b21aba9429fcdb0eea3ae09e64fa",
        1853735,
    ),
    UDFile(
        "UD_Latin-PROIEL",
        "la_proiel-ud-test.conllu",
        "35be241f1b5b47b66c2f222c611dfa80cd0ed9ec2e621fe352e8d4a1875183b4",
        1289508,
    ),
    UDFile(
        "UD_Latin-PROIEL",
        "la_proiel-ud-train.conllu",
        "010188e77944e87d959b578fb746b29c33c1b067dcc5652cbe13c60b40a6d0f6",
        16357842,
    ),
    UDFile(
        "UD_Latin-ITTB",
        "la_ittb-ud-test.conllu",
        "b25d8f12a7f483ff6152ce3b3724aabafffc1336103526229c919808f9de5f1e",
        3184535,
    ),
    UDFile(
        "UD_Latin-ITTB",
        "la_ittb-ud-train.conllu",
        "0f0aded3ec3f697cdb8dc2294d213bdc951b127a5bc3d2114be22cd730cac5b8",
        41138457,
    ),
    UDFile(
        "UD_Latin-LLCT",
        "la_llct-ud-train.conllu",
        "8aabc8735c7a623a9e4820e13861a87459dd0fb5b2d238f0583854143526a643",
        18830634,
    ),
    UDFile(
        "UD_Latin-UDante",
        "la_udante-ud-train.conllu",
        "7308e1b9145bc5c4e6febc1149722a8fed89b2cf5a59a9a83ec53744de57744f",
        3006783,
    ),
    UDFile(
        "UD_Latin-CIRCSE",
        "la_circse-ud-train.conllu",
        "09c44e9453745d9123739c33d12dbcd4fd0f775434d36ab238a6e94179ecf1e8",
        1812102,
    ),
)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def is_valid(path: Path, ud_file: UDFile) -> bool:
    """True if the file has the pinned size and checksum."""
    return path.stat().st_size == ud_file.size and file_sha256(path) == ud_file.sha256


def download(url: str, dest: Path, ud_file: UDFile) -> None:
    part = dest.with_name(dest.name + ".part")
    digest = hashlib.sha256()
    received = 0
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, part.open("wb") as out:
            while chunk := resp.read(CHUNK):
                out.write(chunk)
                digest.update(chunk)
                received += len(chunk)
        if received != ud_file.size:
            raise RuntimeError(
                f"size mismatch: received {received} bytes, expected {ud_file.size}"
            )
        if digest.hexdigest() != ud_file.sha256:
            raise RuntimeError(
                f"checksum mismatch: got {digest.hexdigest()}, expected {ud_file.sha256}"
            )
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    part.replace(dest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=BASE_URL, help="URL template")
    parser.add_argument("--dest-dir", type=Path, default=DEST_DIR)
    parser.add_argument(
        "--force", action="store_true", help="re-download even if present"
    )
    args = parser.parse_args(argv)

    args.dest_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    for ud_file in FILES:
        dest = args.dest_dir / ud_file.name
        if dest.exists() and not args.force:
            if is_valid(dest, ud_file):
                print(f"{dest.name} already present and valid; skipping download.")
                continue
            print(f"{dest.name} exists but does not match the pinned checksum.")
        url = args.base_url.format(
            repo=ud_file.repo, release=RELEASE, name=ud_file.name
        )
        print(f"Downloading {url}")
        try:
            download(url, dest, ud_file)
        except (OSError, RuntimeError, urllib.error.URLError) as e:
            print(f"error: {ud_file.name}: {e}", file=sys.stderr)
            failed += 1
            continue
        print(f"Saved {dest}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
