#!/usr/bin/env python3
"""Rebuild people/index.json from people/*.jsonl.

    python3 tools/build_index.py

The index is what the site loads. Its order decides what a visitor sees first,
so people are ordered by a SHA-256 of their ID rather than by country and
number: the first ID of every country is a woman, and file order put a page of
women at the front. The hash order looks shuffled but is the same every build,
so a link to a page of results keeps meaning the same people.

Deterministic: no timestamp, the same records always give the same bytes.
Standard library only.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PEOPLE = os.path.join(ROOT, "people")
FIELDS = ["id", "country", "name", "native", "sex", "age", "heritage", "household"]


def row(r: dict) -> list:
    hh = r.get("household")
    return [
        r["id"], r["country"], r["name"], r.get("native_name") or "",
        r["sex"], r["age"], r["appearance"]["heritage"],
        hh["id"] if isinstance(hh, dict) else "",
    ]


def main() -> int:
    records = []
    digest = hashlib.sha256()
    for f in sorted(glob.glob(os.path.join(PEOPLE, "*.jsonl"))):
        with open(f, "rb") as fh:
            digest.update(fh.read())
        with open(f, encoding="utf-8") as fh:
            records += [json.loads(ln) for ln in fh if ln.strip()]
    records.sort(key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest())
    index = {
        "source": digest.hexdigest()[:16],
        "count": len(records),
        "sizes": {"s": 256, "m": 512, "l": 1024},
        "format": "avif",
        "fields": FIELDS,
        "people": [row(r) for r in records],
    }
    out = os.path.join(PEOPLE, "index.json")
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(index, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    print(f"wrote {out}: {len(records)} people")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
