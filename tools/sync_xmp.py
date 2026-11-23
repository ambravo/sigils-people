#!/usr/bin/env python3
"""Make the XMP record fields in each portrait match people/*.jsonl.

    python3 tools/sync_xmp.py            report how many portraits differ
    python3 tools/sync_xmp.py --write    rewrite the differing fields

Only the record fields in XMP-sigils are touched (Heritage, NamingCulture, Skin,
HairColor, HairStyle, Build, FacialHair, Headwear). The rendered prompt
(Description), negative, seed, model and RenderKey are what the image was
actually made from, so they are left exactly as they are. Image data is not
re-encoded; exiftool rewrites only the metadata.

Requires exiftool (brew install exiftool). Standard library otherwise.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONFIG = os.path.join(HERE, "exiftool-sigils.config")
SIZES = ("s", "m", "l")
# XMP tag -> function that reads the record value
TAGS = {
    "Heritage": lambda r: r["appearance"].get("heritage"),
    "NamingCulture": lambda r: r.get("naming_culture"),
    "Skin": lambda r: r["appearance"].get("skin"),
    "HairColor": lambda r: r["appearance"].get("hair_color"),
    "HairStyle": lambda r: r["appearance"].get("hair_style"),
    "Build": lambda r: r["appearance"].get("build"),
    "FacialHair": lambda r: r["appearance"].get("facial_hair"),
    "Headwear": lambda r: r["appearance"].get("headwear"),
}


def load_records() -> dict[str, dict]:
    recs = {}
    for f in glob.glob(os.path.join(ROOT, "people", "*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip():
                    r = json.loads(ln)
                    recs[r["id"]] = r
    return recs


def read_xmp(folder: str) -> list[dict]:
    out = subprocess.check_output(
        ["exiftool", "-j", "-r", "-n0"] + [f"-{t}" for t in TAGS] + [folder],
        text=True)
    return json.loads(out)


def main() -> int:
    write = "--write" in sys.argv
    recs = load_records()
    commands: list[str] = []
    files_changed = 0
    tags_changed = 0
    for size in SIZES:
        folder = os.path.join(ROOT, "portraits", size)
        for row in read_xmp(folder):
            pid = os.path.splitext(os.path.basename(row["SourceFile"]))[0]
            r = recs.get(pid)
            if r is None:
                continue
            diffs = []
            for tag, get in TAGS.items():
                want = get(r)
                if want is None:
                    continue
                have = row.get(tag)
                if have is None or str(have) != str(want):
                    diffs.append((tag, want))
            if diffs:
                files_changed += 1
                tags_changed += len(diffs)
                for tag, want in diffs:
                    commands.append(f"-XMP-sigils:{tag}={want}")
                commands.append(row["SourceFile"])
                commands.append("-execute")
    print(f"{files_changed} portraits differ from their record; {tags_changed} fields to write")
    if not write or not commands:
        print("dry run; pass --write to change the portraits" if not write else "nothing to write")
        return 0
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".args", delete=False) as fh:
        fh.write("\n".join(commands) + "\n")
        args = fh.name
    try:
        subprocess.run(["exiftool", "-config", CONFIG, "-overwrite_original", "-charset", "filename=utf8",
                        "-charset", "exiftool=utf8", "-q", "-@", args], check=True)
    finally:
        os.unlink(args)
    print("written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
