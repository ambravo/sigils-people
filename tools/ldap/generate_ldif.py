#!/usr/bin/env python3
"""Generate an LDIF import of the sigils people for an LDAP directory.

    python3 tools/ldap/generate_ldif.py -o cast.ldif
    python3 tools/ldap/generate_ldif.py --country AF --country BT --limit 40

The output is a pure function of people/*.jsonl and the options given: no
timestamps, no randomness, entries in a fixed order. Running it twice gives the
same bytes, and the header carries a digest of the input so a directory can
tell which cast it was loaded from.

Layout under the base DN (default dc=sigils,dc=test):

    dc=sigils,dc=test                     the base entry (organization)
    ou=people,<base>                      container
    ou=<CC>,ou=people,<base>              one per country, description = name
    uid=<id>,ou=<CC>,ou=people,<base>     one inetOrgPerson per person
    cn=<household>,ou=<CC>,ou=people,... one groupOfNames per household

Mapping from the record (see tools/ldap/README.md for the reasons):

    uid, cn, displayName   id, name, name
    givenName              given_names joined with spaces (omitted if none)
    sn                     family_names, else patronymic, else the name's last word
    cn;x-native            native_name, when present
    mail                   <id>@sigils.test (reserved domain, never delivered)
    labeledURI             the m-size portrait, AVIF
    description            age=, sex=, heritage=, naming-culture=, document-sex=,
                           patronymic=, household=<id> role=<role>

No userPassword is written. Load targets that need credentials set them at load time.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ldif import encode_attr, make_dn  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_PEOPLE = REPO / "people"
DEFAULT_BASE = "dc=sigils,dc=test"
DEFAULT_PORTRAITS = "https://cdn.jsdelivr.net/gh/ambravo/sigils-people@main/portraits/m"
MAIL_DOMAIN = "sigils.test"
GENERATOR_VERSION = "1"

Entry = tuple[str, list[tuple[str, str]]]  # (dn, [(attribute, value), ...])


def parse_base(base: str) -> list[tuple[str, str]]:
    """Split a base DN into RDNs. Only dc= components are supported."""
    rdns = []
    for part in base.split(","):
        attr, sep, value = part.strip().partition("=")
        if not sep or attr.lower() != "dc" or not value:
            raise ValueError(f"base DN must be made of dc= components: {base!r}")
        rdns.append(("dc", value))
    if not rdns:
        raise ValueError("empty base DN")
    return rdns


def load_records(people_dir: Path) -> tuple[list[dict], str]:
    """All records, sorted by country then id, and a digest of the input bytes."""
    digest = hashlib.sha256()
    records = []
    for path in sorted(people_dir.glob("*.jsonl")):
        data = path.read_bytes()
        digest.update(data)
        for line in data.decode("utf-8").splitlines():
            if line.strip():
                records.append(json.loads(line))
    records.sort(key=lambda r: (r["country"], r["id"]))
    return records, digest.hexdigest()[:16]


def load_country_names(people_dir: Path) -> dict[str, str]:
    path = people_dir / "countries.json"
    if not path.exists():
        return {}
    return {code: info["name"] for code, info in json.loads(path.read_text("utf-8")).items()}


def surname(rec: dict) -> str:
    """sn is required by inetOrgPerson, so it always gets a value."""
    family = " ".join(rec.get("family_names") or [])
    if family:
        return family
    patronymic = rec.get("patronymic") or ""
    if patronymic:
        return patronymic
    words = rec["name"].split()
    return words[-1] if words else rec["id"]


def person_entry(rec: dict, base_rdns: list[tuple[str, str]], portrait_base: str) -> Entry:
    """One inetOrgPerson under its country's OU."""
    cc = rec["country"]
    dn = make_dn([("uid", rec["id"]), ("ou", cc), ("ou", "people"), *base_rdns])
    given = " ".join(rec.get("given_names") or [])
    attrs: list[tuple[str, str]] = [
        ("objectClass", "top"),
        ("objectClass", "person"),
        ("objectClass", "organizationalPerson"),
        ("objectClass", "inetOrgPerson"),
        ("uid", rec["id"]),
        ("cn", rec["name"]),
        ("sn", surname(rec)),
    ]
    if given:
        attrs.append(("givenName", given))
    attrs.append(("displayName", rec["name"]))
    if rec.get("native_name"):
        attrs.append(("cn;x-native", rec["native_name"]))
    attrs.append(("mail", f"{rec['id']}@{MAIL_DOMAIN}"))
    attrs.append(("labeledURI", f"{portrait_base}/{rec['id']}.avif"))

    appearance_heritage = (rec.get("appearance") or {}).get("heritage") or rec.get("naming_culture")
    attrs.append(("description", f"age={rec['age']}"))
    attrs.append(("description", f"sex={rec['sex']}"))
    if rec.get("document_sex"):
        attrs.append(("description", f"document-sex={rec['document_sex']}"))
    if appearance_heritage:
        attrs.append(("description", f"heritage={appearance_heritage}"))
    if rec.get("naming_culture"):
        attrs.append(("description", f"naming-culture={rec['naming_culture']}"))
    if rec.get("patronymic"):
        attrs.append(("description", f"patronymic={rec['patronymic']}"))
    household = rec.get("household")
    if household:
        attrs.append(("description", f"household={household['id']} role={household['role']}"))
    return dn, attrs


def household_entries(
    records: list[dict], base_rdns: list[tuple[str, str]]
) -> list[Entry]:
    """One groupOfNames per household, listing the people actually emitted."""
    groups: dict[str, list[str]] = {}
    country_of: dict[str, str] = {}
    for rec in records:
        household = rec.get("household")
        if household:
            groups.setdefault(household["id"], []).append(rec["id"])
            country_of[household["id"]] = rec["country"]
    out: list[Entry] = []
    for hh_id in sorted(groups):
        members = sorted(groups[hh_id])
        cc = country_of[hh_id]
        dn = make_dn([("cn", hh_id), ("ou", cc), ("ou", "people"), *base_rdns])
        attrs = [("objectClass", "top"), ("objectClass", "groupOfNames"), ("cn", hh_id)]
        for member in members:
            attrs.append(("member", make_dn([("uid", member), ("ou", cc), ("ou", "people"), *base_rdns])))
        attrs.append(("description", f"household {hh_id}, {len(members)} members"))
        out.append((dn, attrs))
    return out


def build_entries(
    records: list[dict],
    country_names: dict[str, str],
    base: str,
    portrait_base: str,
) -> list[Entry]:
    base_rdns = parse_base(base)
    entries: list[Entry] = []
    head_name = base_rdns[0][1]
    entries.append((
        make_dn(base_rdns),
        [("objectClass", "top"), ("objectClass", "dcObject"), ("objectClass", "organization"),
         ("dc", head_name), ("o", head_name)],
    ))
    entries.append((
        make_dn([("ou", "people"), *base_rdns]),
        [("objectClass", "top"), ("objectClass", "organizationalUnit"), ("ou", "people")],
    ))

    by_country: dict[str, list[dict]] = {}
    for rec in records:
        by_country.setdefault(rec["country"], []).append(rec)
    for cc in sorted(by_country):
        entries.append((
            make_dn([("ou", cc), ("ou", "people"), *base_rdns]),
            [("objectClass", "top"), ("objectClass", "organizationalUnit"), ("ou", cc),
             ("description", country_names.get(cc, cc))],
        ))
        for rec in by_country[cc]:
            entries.append(person_entry(rec, base_rdns, portrait_base))
        entries.extend(household_entries(by_country[cc], base_rdns))
    return entries


def render(entries: list[Entry], header: list[str]) -> str:
    lines = [f"# {h}" for h in header] + ["version: 1", ""]
    for dn, attrs in entries:
        lines.append(encode_attr("dn", dn))
        for name, value in attrs:
            lines.append(encode_attr(name, value))
        lines.append("")
    return "\n".join(lines) + "\n"


def select(records: list[dict], countries: list[str] | None, limit: int | None) -> list[dict]:
    if countries:
        wanted = {c.upper() for c in countries}
        unknown = wanted - {r["country"] for r in records}
        if unknown:
            raise SystemExit(f"no records for country code(s): {', '.join(sorted(unknown))}")
        records = [r for r in records if r["country"] in wanted]
    if limit is not None:
        records = records[:limit]
    return records


def generate(
    people_dir: Path = DEFAULT_PEOPLE,
    base: str = DEFAULT_BASE,
    portrait_base: str = DEFAULT_PORTRAITS,
    countries: list[str] | None = None,
    limit: int | None = None,
) -> tuple[str, dict]:
    records, digest = load_records(people_dir)
    records = select(records, countries, limit)
    names = load_country_names(people_dir)
    entries = build_entries(records, names, base, portrait_base)
    stats = {
        "people": len(records),
        "countries": len({r["country"] for r in records}),
        "households": len({r["household"]["id"] for r in records if r.get("household")}),
        "entries": len(entries),
    }
    header = [
        "sigils-people LDAP import",
        f"generator: {GENERATOR_VERSION}",
        f"source: {digest}",
        f"base: {base}",
        f"people: {stats['people']}  households: {stats['households']}  countries: {stats['countries']}",
    ]
    return render(entries, header), stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("-o", "--out", type=Path, help="write here instead of stdout")
    ap.add_argument("--people", type=Path, default=DEFAULT_PEOPLE, help="directory of *.jsonl records")
    ap.add_argument("--base-dn", default=DEFAULT_BASE, help=f"base DN (default {DEFAULT_BASE})")
    ap.add_argument("--portraits", default=DEFAULT_PORTRAITS,
                    help="URL prefix for portraits; <id>.avif is appended")
    ap.add_argument("--country", action="append", metavar="CC",
                    help="only this country (repeatable)")
    ap.add_argument("--limit", type=int, help="only the first N people in sorted order")
    args = ap.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        ap.error("--limit must be at least 1")

    text, stats = generate(args.people, args.base_dn, args.portraits, args.country, args.limit)
    if args.out:
        args.out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}: {stats}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
