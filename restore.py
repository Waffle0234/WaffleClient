#!/usr/bin/env python3
"""Rebuild the Kiln repository from the kiln-*.txt bundle files.

    python3 restore.py [--from DIR] [--to DIR] [--no-git] [--force]

--from  folder holding the bundles (default: the folder containing this script)
--to    folder to create (default: ./kiln)

Binary files (icons) are not bundled: run tools/regen_icons.py afterwards.
"""
import argparse
import pathlib
import re
import subprocess
import sys
import urllib.request

ENTRY = re.compile(r"^<<<<<KILN-FILE (.+?)>>>>>\n(.*?)\n<<<<<KILN-END>>>>>\n", re.M | re.S)
LICENSE_URL = "https://raw.githubusercontent.com/spdx/license-list-data/main/text/GPL-3.0-only.txt"


def safe_destination(root: pathlib.Path, rel: str) -> pathlib.Path:
    """Bundle contents are untrusted input: refuse anything that could leave `root`."""
    posix = pathlib.PurePosixPath(rel)
    if not rel or "\\" in rel or "\0" in rel or posix.is_absolute() or ".." in posix.parts:
        sys.exit(f"refusing unsafe path in bundle: {rel!r}")
    dest = root.joinpath(*posix.parts).resolve()
    if root not in dest.parents:
        sys.exit(f"refusing path that escapes the target folder: {rel!r}")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--from", dest="src", default=str(pathlib.Path(__file__).resolve().parent))
    ap.add_argument("--to", dest="dst", default="kiln")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--force", action="store_true", help="write into a non-empty folder")
    args = ap.parse_args()

    bundles = sorted(pathlib.Path(args.src).glob("kiln-*.txt"))
    if not bundles:
        sys.exit(f"no kiln-*.txt bundle files found in {args.src}")

    root = pathlib.Path(args.dst).resolve()
    if root.exists() and any(root.iterdir()) and not args.force:
        sys.exit(f"{root} is not empty; choose another --to folder or pass --force")
    root.mkdir(parents=True, exist_ok=True)

    written = 0
    for bundle in bundles:
        # Decode raw bytes (no newline translation) so files come out exactly as bundled.
        text = bundle.read_bytes().decode("utf-8")
        count = 0
        for match in ENTRY.finditer(text):
            dest = safe_destination(root, match.group(1))
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(match.group(2).encode("utf-8"))
            count += 1
        print(f"{bundle.name}: {count} files")
        written += count
    print(f"restored {written} files into {root}")

    if not (root / "LICENSE").exists():
        try:
            with urllib.request.urlopen(LICENSE_URL, timeout=20) as r:
                (root / "LICENSE").write_bytes(r.read())
            print("fetched LICENSE (GPL-3.0-only)")
        except OSError as e:
            print(f"note: could not fetch LICENSE ({e}); download {LICENSE_URL}")

    if not args.no_git and not (root / ".git").exists():
        try:
            run = lambda *a: subprocess.run(["git", "-C", str(root), *a], check=True, capture_output=True)
            run("init", "-q")
            run("add", "-A")
            run("-c", "user.name=kiln-dev", "-c", "user.email=dev@kiln.invalid",
                "commit", "-q", "-m", "Baseline restored from bundles")
            print("created a baseline git commit")
        except (OSError, subprocess.CalledProcessError):
            print("note: git is unavailable; run `git init` yourself")

    print("next: cd", root.name, "&& (cd ui && npm ci) && pip install pillow && python3 tools/regen_icons.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
