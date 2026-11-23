#!/usr/bin/env python3
"""Normalise the free-text categories in people/*.jsonl.

    python3 tools/normalize_metadata.py            report what would change
    python3 tools/normalize_metadata.py --write    rewrite the files

Four things happen, in this order:

1. Religion is removed from heritage and naming culture: "Palestinian Muslim"
   becomes "Palestinian". Values where nothing is left are reported, not changed.
2. Headwear and hair terms that name a religious garment are replaced with a
   neutral one: hijab and tudung become headscarf; ghutra, turban and cloth wraps
   become headwrap.
3. British spelling and explicit synonyms are unified (see the tables below).
4. Values that differ only in case or separator (space, hyphen, underscore)
   are unified to the most frequent spelling. Heritage and naming culture get
   their first letter capitalised; appearance values are lower case.

Deterministic: the same input always gives the same output. Standard library only.
"""

from __future__ import annotations

import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PEOPLE = os.path.join(ROOT, "people")

APPEARANCE = ("skin", "hair_color", "hair_style", "facial_hair", "headwear", "build")
PROPER_HERITAGE = ("heritage",)            # appearance.heritage
PROPER_TOP = ("naming_culture",)           # top-level

# -- 1. religion ---------------------------------------------------------------

RELIGIOUS_WORDS = r"\b(Muslim|Christian|Jewish|Hindu|Sikh|Islamic|Catholic|Orthodox|Maronite)\b"
RELIGION_SPECIAL = {                       # where removal alone gives the wrong word
    "Hindu/North": "North Indian",
    "Mozambican Muslim North": "Northern Mozambican",
}

# -- 2. religious garments -----------------------------------------------------

GARMENT = [
    (r"\b(hijab|tudung)\b", "headscarf"),
    (r"\bghutra\b", "headwrap"),
    (r"\b(cloth )?turban\b", "headwrap"),
    (r"\bheadcloth\b", "headwrap"),
    (r"\b(cloth wrap|wrapped cloth|wraparound|cloth headwrap)\b", "headwrap"),
]

# -- 3. British spelling and synonyms ------------------------------------------

BRITISH = [
    (r"\bgray\b", "grey"), (r"\bgraying\b", "greying"),
    (r"\bmustache\b", "moustache"), (r"\bcolored\b", "coloured"),
    (r"\bcolorful\b", "colourful"), (r"\bcolor\b", "colour"),
    (r"\bblond\b", "blonde"), (r"\bcenter\b", "centre"),
    (r"\bfavor\b", "favour"), (r"\bhonor\b", "honour"),
]
LEADING_ARTICLE = r"^(a|an) "

VALUE_SYNONYMS = {
    "hair_color": {
        "grey-black": "black with grey", "grey-brown": "brown with grey",
        "greying brown": "brown with grey", "white-grey": "white with grey",
        "chestnut brown": "chestnut", "medium brown": "brown",
    },
    "facial_hair": {
        "clean": "clean-shaven", "neatly trimmed beard": "trimmed beard",
        "neatly trimmed moustache": "trimmed moustache", "close trimmed": "close-trimmed beard",
    },
    "skin": {"deep": "deep brown", "medium to dark": "medium-dark", "very fair": "fair"},
    "hair_style": {"braids": "braided", "braids wrapped": "braided wrapped",
                   "braided wrap": "braided wrapped", "wrapped cloth": "wrapped",
                   "braided wrapped cloth": "braided wrapped",
                   "long braided wrapped cloth": "long braided wrapped"},
}
BUILD_WHOLE = {"trim and muscular": "athletic", "soft and round": "full-figured",
               "broad and heavy": "heavyset"}
BUILD_BODY = {"heavy": "heavyset", "stout": "heavyset", "thickset": "stocky",
              "solid": "sturdy", "slight": "slim", "rounded": "full-figured",
              "average": "medium"}


def religion(value: str) -> str | None:
    """The value without religion; None when a religious value has nothing left.

    A value with no religious word is returned unchanged.
    """
    if value in RELIGION_SPECIAL:
        return RELIGION_SPECIAL[value]
    if not re.search(RELIGIOUS_WORDS, value):
        return value
    out = re.sub(RELIGIOUS_WORDS, "", value)
    out = re.sub(r"\s*/\s*", " ", out)
    out = re.sub(r"\s+,", ",", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" -/,")
    return out or None


def build(value: str) -> str:
    if value in BUILD_WHOLE:
        return BUILD_WHOLE[value]
    m = re.match(r"^(tall|short) and (.+)$", value)
    if m and m.group(2) in BUILD_BODY:
        return f"{m.group(1)} and {BUILD_BODY[m.group(2)]}"
    return BUILD_BODY.get(value, value)


def british(value: str, proper: bool = False) -> str:
    """Spelling only. Proper categories (heritage, naming) are left alone: "Coloured"
    there is a South African term, not the colour word."""
    if proper:
        return value
    for pattern, repl in BRITISH:
        value = re.sub(pattern, repl, value, flags=re.IGNORECASE)
    return value


def garments(value: str) -> str:
    for pattern, repl in GARMENT:
        value = re.sub(pattern, repl, value, flags=re.IGNORECASE)
    return value


def synonyms(field: str, value: str) -> str:
    if field == "build":
        return build(value)
    value = re.sub(LEADING_ARTICLE, "", value)
    return VALUE_SYNONYMS.get(field, {}).get(value, value)


# -- 4. case and separators ----------------------------------------------------

SEP = re.compile(r"[\s_\-]+")


def group_key(s: str) -> str:
    return SEP.sub(" ", s).strip().casefold()


def cap_first(s: str) -> str:
    # "iTaukei" keeps its lower-case first letter; a camel-case start is deliberate.
    if re.match(r"^[a-z][A-Z]", s):
        return s
    return s[:1].upper() + s[1:]


SMALL = {"of", "and", "de", "la", "du", "von", "van", "der", "da", "do", "a"}


def title_lower(s: str) -> str:
    """Capitalise each word of an all-lower-case value; small words stay lower."""
    out, first = [], True
    for w in re.split(r"(\s|-)", s):
        if w in ("", " ", "-"):
            out.append(w)
            continue
        out.append(w if (not first and w in SMALL) else w[:1].upper() + w[1:])
        first = False
    return "".join(out)


def canonical_map(values: collections.Counter, proper: bool) -> dict[str, str]:
    groups: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for v, n in values.items():
        spelled = v.replace("_", " ").strip()
        if proper:
            spelled = title_lower(spelled) if spelled == spelled.lower() else cap_first(spelled)
        groups[group_key(v)][spelled] += n
    mapping = {}
    for members in groups.values():
        best = max(members.items(), key=lambda vn: (vn[1], "-" in vn[0], vn[0]))[0]
        if not proper:
            best = best.casefold()
        for v in values:
            if group_key(v) == group_key(best):
                mapping[v] = best
    return mapping


def main() -> int:
    write = "--write" in sys.argv
    files = sorted(glob.glob(os.path.join(PEOPLE, "*.jsonl")))
    rows = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            for ln in fh.read().split("\n"):
                if ln.strip():
                    rows.append((f, json.loads(ln)))

    changes = collections.Counter()
    unresolved = collections.Counter()

    def set_value(holder: dict, field: str, new: str, old: str, tag: str):
        if new != old:
            changes[(field, old, new)] += 1
            holder[field] = new

    # Step 1, for values where religion leaves nothing: the other field is used
    # when it is not religious (Muslim heritage with naming "Indian" becomes "Indian";
    # naming "Christian" with heritage "Goan" becomes "Goan").
    for _, r in rows:
        app = r["appearance"]
        nc = r.get("naming_culture") or ""
        hv = app.get("heritage") or ""
        nc_clean = religion(nc) if nc and nc.upper() != r["country"] else None
        h_clean = religion(hv) if hv else None
        if hv and h_clean is None and nc_clean and nc_clean == nc:
            app["heritage"] = nc_clean
            changes[("heritage", hv, nc_clean)] += 1
        if nc and nc.upper() != r["country"] and nc_clean is None and h_clean and h_clean == hv:
            r["naming_culture"] = h_clean
            changes[("naming_culture", nc, h_clean)] += 1

    # Steps 1-3: per-value rewrites.
    for _, r in rows:
        app = r["appearance"]
        v = app.get("heritage")
        if v:
            new = religion(v)
            if new is None:
                unresolved[("heritage", v)] += 1
            else:
                set_value(app, "heritage", british(new, proper=True), v, "heritage")
        nc = r.get("naming_culture")
        if nc and nc.upper() != r["country"]:
            new = religion(nc)
            if new is None:
                unresolved[("naming_culture", nc)] += 1
            else:
                set_value(r, "naming_culture", british(new, proper=True), nc, "naming_culture")
        for field in APPEARANCE:
            v = app.get(field)
            if not v:
                continue
            new = garments(synonyms(field, british(v)))
            set_value(app, field, new, v, field)

    # Step 4: one spelling per value.
    maps = {}
    for field in APPEARANCE + PROPER_HERITAGE:
        vals = collections.Counter(
            r["appearance"].get(field) for _, r in rows
            if isinstance(r.get("appearance"), dict) and r["appearance"].get(field))
        maps[("appearance", field)] = canonical_map(vals, field in PROPER_HERITAGE)
    for field in PROPER_TOP:
        vals = collections.Counter(
            r.get(field) for _, r in rows
            if r.get(field) and r[field].upper() != r["country"])
        maps[("top", field)] = canonical_map(vals, True)

    by_file = collections.defaultdict(list)
    for f, r in rows:
        for (where, field), mapping in maps.items():
            holder = r["appearance"] if where == "appearance" else r
            v = holder.get(field)
            if where == "top" and v and v.upper() == r["country"]:
                continue
            if v and mapping.get(v, v) != v:
                changes[(field, v, mapping[v])] += 1
                holder[field] = mapping[v]
        by_file[f].append(r)

    codes = sum(1 for _, r in rows if (r.get("naming_culture") or "").upper() == r["country"])
    print(f"{codes} naming_culture values equal their own country code and are left unchanged")
    print(f"{sum(changes.values())} values change across {len(changes)} spellings")
    for (field, old, new), n in sorted(changes.items()):
        print(f"  {field:14} {old!r:40} -> {new!r}  ({n})")
    if unresolved:
        print(f"{sum(unresolved.values())} religious values have nothing left once religion is removed; unchanged:")
        for (field, old), n in sorted(unresolved.items()):
            print(f"  {field:14} {old!r}  ({n})")

    if write:
        for f in files:
            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                for r in by_file[f]:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("written")
    else:
        print("dry run; pass --write to change the files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
