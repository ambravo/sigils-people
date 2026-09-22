#!/usr/bin/env python3
"""Check people files against the contract this repository publishes.

    python3 check.py                     every country
    python3 check.py people/np.jsonl     one

Run this before opening a pull request. It checks the things a consumer of this
data is entitled to assume: that ids are well formed and complete, that the
composition of a country is what the README says it is, that names are unique
across the whole cast, and that every person has a portrait in all three sizes.

Standard library only. Exit status 0 means everything passed.
"""

from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys
import unicodedata

PER_COUNTRY = 20
SIZES = ("s", "m", "l")
FILE_RE = re.compile(r"^([a-z]{2})\.jsonl$")
SEXES = {"female", "male"}
MARKERS = {"F", "M", "X", "O"}
SLOTS = {"individual", "household", "coverage"}
BANDS = ((18, 29), (30, 44), (45, 64), (65, 200))
APPEARANCE_KEYS = {"heritage", "skin", "hair_color", "hair_style",
                   "facial_hair", "glasses", "headwear", "build"}
REQUIRED = ("id", "country", "sex", "age", "name", "given_names", "family_names",
            "naming_culture", "document_sex", "slot", "household", "appearance")
# A profile picture shows the face. Headwear may cover the hair, never the face.
FACE_COVERING = re.compile(
    r"niqab|burqa|burka|face veil|veiled face|mask|balaclava|covering (the|her|his) face", re.I)

HERE = os.path.dirname(os.path.abspath(__file__))


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if not unicodedata.combining(c))


def check_record(cc: str, n: int, r: dict) -> list[str]:
    where = f"line {n}"
    errs = []
    missing = [k for k in REQUIRED if k not in r]
    if missing:
        return [f"{where}: missing {', '.join(missing)}"]
    if r["id"] != f"{cc}-{n:02d}":
        errs.append(f"{where}: id must be {cc}-{n:02d} — ids run {cc}-01 to {cc}-{PER_COUNTRY} in order")
    if r["country"] != cc.upper():
        errs.append(f"{where}: country must be {cc.upper()}")
    if r["sex"] not in SEXES:
        errs.append(f"{where}: sex must be female or male "
                    "(a non-binary marker belongs in document_sex)")
    if r["document_sex"] not in MARKERS:
        errs.append(f"{where}: document_sex must be one of {', '.join(sorted(MARKERS))}")
    if not isinstance(r["age"], int) or not 0 <= r["age"] <= 105:
        errs.append(f"{where}: age must be a whole number from 0 to 105")
    if not isinstance(r["name"], str) or not r["name"].strip():
        errs.append(f"{where}: name must be a non-empty string")
    if not isinstance(r["given_names"], list) or not r["given_names"]:
        errs.append(f"{where}: given_names must be a non-empty list")
    if not isinstance(r["family_names"], list):
        errs.append(f"{where}: family_names must be a list (empty for a mononym)")
    # The display name and the parts must agree, diacritics included.
    if isinstance(r["name"], str):
        flat = strip_accents(r["name"]).lower()
        for part in [*(r.get("given_names") or []), *(r.get("family_names") or [])]:
            if isinstance(part, str) and strip_accents(part).lower() not in flat:
                errs.append(f"{where}: name {r['name']!r} does not contain {part!r} "
                            "from its own given_names/family_names")
    if r["slot"] not in SLOTS:
        errs.append(f"{where}: slot must be one of {', '.join(sorted(SLOTS))}")
    a = r["appearance"]
    if not isinstance(a, dict):
        errs.append(f"{where}: appearance must be an object")
    else:
        unknown = sorted(set(a) - APPEARANCE_KEYS)
        if unknown:
            errs.append(f"{where}: appearance has unknown keys: {', '.join(unknown)}")
        for k in ("heritage", "skin", "build"):
            if not isinstance(a.get(k), str) or not a[k].strip():
                errs.append(f"{where}: appearance.{k} must be a non-empty string")
        if "glasses" in a and not isinstance(a["glasses"], bool):
            errs.append(f"{where}: appearance.glasses must be true or false")
        head = a.get("headwear")
        if isinstance(head, str) and FACE_COVERING.search(head):
            errs.append(f"{where}: headwear {head!r} covers the face — "
                        "a portrait must show it")
    return errs


def check_file(path: str) -> tuple[list[str], list[dict]]:
    name = os.path.basename(path)
    m = FILE_RE.match(name)
    if not m:
        return [f"{path}: must be named <two-letter country code>.jsonl, lowercase"], []
    cc = m.group(1)
    errs, records = [], []
    lines = [ln for ln in open(path, encoding="utf-8").read().splitlines() if ln.strip()]
    for n, line in enumerate(lines, 1):
        try:
            r = json.loads(line)
        except json.JSONDecodeError as e:
            errs.append(f"line {n}: {e}")
            continue
        if not isinstance(r, dict):
            errs.append(f"line {n}: not a JSON object")
            continue
        records.append(r)
        errs.extend(check_record(cc, n, r))
    if len(lines) != PER_COUNTRY:
        errs.append(f"{len(lines)} people; a country has exactly {PER_COUNTRY}")

    ok = [r for r in records if isinstance(r.get("age"), int) and r.get("sex") in SEXES]
    individuals = [r for r in ok if r.get("slot") == "individual"]
    if len(individuals) != 8:
        errs.append(f"{len(individuals)} individuals; there are exactly 8 — one woman "
                    "and one man in each band 18–29, 30–44, 45–64, 65+")
    for lo, hi in BANDS:
        for sex in sorted(SEXES):
            if not any(lo <= r["age"] <= hi and r["sex"] == sex for r in individuals):
                errs.append(f"no {sex} individual aged {lo}–{min(hi, 105)}")
    homes: dict[str, list[dict]] = {}
    for r in ok:
        if r.get("slot") == "household" and isinstance(r.get("household"), dict):
            homes.setdefault(r["household"].get("id"), []).append(r)
    if len(homes) < 2:
        errs.append(f"{len(homes)} households; a country has two")
    for hid, members in sorted(homes.items(), key=lambda kv: str(kv[0])):
        if len(members) < 2:
            errs.append(f"household {hid} has one member")
        if not any(m["age"] >= 18 for m in members):
            errs.append(f"household {hid} has no adult")
    return errs, records


def main(argv: list[str]) -> int:
    paths = argv[1:] or sorted(glob.glob(os.path.join(HERE, "people", "*.jsonl")))
    if not paths:
        print("no people files found", file=sys.stderr)
        return 1

    failed = 0
    everyone: list[dict] = []
    for path in paths:
        errs, records = check_file(path)
        everyone.extend(records)
        if errs:
            failed += 1
            print(f"✗ {path}")
            for e in errs:
                print(f"    {e}")
        else:
            print(f"✓ {path}")

    # Across the whole cast, not just within a file.
    names = [r.get("name") for r in everyone if isinstance(r.get("name"), str)]
    dupes = sorted({x for x in names if names.count(x) > 1})
    if dupes:
        failed += 1
        print(f"✗ names used more than once: {', '.join(dupes[:10])}"
              + (f" (+{len(dupes) - 10} more)" if len(dupes) > 10 else ""))

    ids = [r.get("id") for r in everyone if isinstance(r.get("id"), str)]
    dup_ids = sorted({x for x in ids if ids.count(x) > 1})
    if dup_ids:
        failed += 1
        print(f"✗ ids used more than once: {', '.join(dup_ids[:10])}")

    # Only meaningful over the whole cast; one file names 20 of 11,880 portraits.
    if len(paths) > 1:
        missing = [f"{size}/{pid}.avif" for pid in ids for size in SIZES
                   if not os.path.exists(os.path.join(HERE, "portraits", size, f"{pid}.avif"))]
        if missing:
            failed += 1
            print(f"✗ {len(missing)} portraits missing: {', '.join(missing[:6])}"
                  + (" …" if len(missing) > 6 else ""))
        known = set(ids)
        orphans = sorted(os.path.basename(p)[:-5]
                         for p in glob.glob(os.path.join(HERE, "portraits", "s", "*.avif"))
                         if os.path.basename(p)[:-5] not in known)
        if orphans:
            failed += 1
            print(f"✗ {len(orphans)} portraits have no record: {', '.join(orphans[:6])}")

    print(f"\n{len(everyone)} people in {len(paths)} files · "
          + ("everything passed" if not failed else f"{failed} problems"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
