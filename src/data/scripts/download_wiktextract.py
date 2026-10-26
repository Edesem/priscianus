"""Download the Wiktextract Latin dump from kaikki.org into src/data/raw/.

Idempotent: if the dump is already present and passes verification, nothing is
downloaded. Standard library only, so it runs without installing the backend.

Verification:
  * download: bytes received must equal the server's Content-Length
  * existing file: must be non-empty and end with a complete JSON line
    (catches truncated files)

The dump is regenerated upstream every few weeks, so its size and checksum are
not pinned. The upstream Last-Modified date is saved beside the dump.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

URL = "https://kaikki.org/dictionary/Latin/kaikki.org-dictionary-Latin.jsonl"
RAW_DIR = Path(__file__).resolve().parents[1] / "raw"
FILENAME = "kaikki.org-dictionary-Latin.jsonl"
CHUNK = 1 << 20
TAIL_BYTES = 1 << 16


def is_complete(path: Path) -> bool:
    """True if the file is non-empty and its last line is a complete JSON object."""
    size = path.stat().st_size
    if size == 0:
        return False
    with path.open("rb") as f:
        f.seek(max(0, size - TAIL_BYTES))
        tail = f.read().rstrip(b"\n")
    last_line = tail.rsplit(b"\n", 1)[-1]
    try:
        return isinstance(json.loads(last_line), dict)
    except ValueError:
        return False


def download(url: str, dest: Path) -> None:
    part = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=60) as resp:
        expected = int(resp.headers["Content-Length"])
        last_modified = resp.headers.get("Last-Modified", "unknown")
        received = 0
        with part.open("wb") as out:
            while chunk := resp.read(CHUNK):
                out.write(chunk)
                received += len(chunk)
                print(
                    f"\r  {received / 1e6:8.1f} / {expected / 1e6:.1f} MB",
                    end="",
                    flush=True,
                )
    print()
    if received != expected:
        part.unlink()
        raise RuntimeError(
            f"size mismatch: received {received} bytes, expected {expected}"
        )
    if not is_complete(part):
        part.unlink()
        raise RuntimeError("downloaded file does not end with a complete JSON line")
    part.replace(dest)
    dest.with_name(dest.name + ".meta.json").write_text(
        json.dumps(
            {"url": url, "last_modified": last_modified, "bytes": received}, indent=2
        )
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default=URL)
    parser.add_argument("--dest-dir", type=Path, default=RAW_DIR)
    parser.add_argument(
        "--force", action="store_true", help="re-download even if present"
    )
    args = parser.parse_args(argv)

    args.dest_dir.mkdir(parents=True, exist_ok=True)
    dest = args.dest_dir / FILENAME

    if dest.exists() and not args.force:
        if is_complete(dest):
            print(f"{dest} already present and valid; skipping download.")
            return 0
        print(f"{dest} exists but looks truncated; re-downloading.")

    print(f"Downloading {args.url}")
    try:
        download(args.url, dest)
    except (OSError, RuntimeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Saved {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
