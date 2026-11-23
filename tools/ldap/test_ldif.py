"""Tests for the LDIF encoder and the generator. Standard library only.

    python3 -m unittest discover -s tools/ldap -v
"""

from __future__ import annotations

import base64
import hashlib
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import generate_ldif as gen  # noqa: E402
from ldif import encode_attr, escape_dn_value, fold, make_dn, needs_base64, parse_ldif  # noqa: E402


def decode_value(line: str) -> str:
    """Parse one encoded attribute line back to its value."""
    entries = parse_ldif(line + "\n\n")
    assert len(entries) == 1 and len(entries[0]) == 1, entries
    return entries[0][0][1]


class EncodingTests(unittest.TestCase):
    def roundtrip(self, value: str) -> None:
        line = encode_attr("cn", value)
        self.assertEqual(decode_value(line), value, msg=repr(value))
        for physical in line.split("\n"):
            self.assertLessEqual(len(physical), 76, msg=repr(physical))

    def test_plain_values_stay_plain(self):
        self.assertEqual(encode_attr("cn", "Emma Johnson"), "cn: Emma Johnson")
        self.assertFalse(needs_base64("Emma Johnson"))

    def test_empty_value(self):
        self.assertEqual(encode_attr("description", ""), "description:")
        self.assertEqual(decode_value("description:"), "")

    def test_unsafe_leading_characters_go_base64(self):
        for value in [" leading space", ":colon", "<angle", "trailing "]:
            self.assertTrue(needs_base64(value), msg=value)
            self.roundtrip(value)

    def test_nul_lf_cr_and_tab(self):
        self.assertTrue(needs_base64("a\x00b"))
        self.assertTrue(needs_base64("a\nb"))
        self.assertTrue(needs_base64("a\rb"))
        self.assertFalse(needs_base64("a\tb"))  # tab is SAFE-CHAR
        self.roundtrip("a\tb")

    def test_non_ascii_always_base64(self):
        for value in ["刘备", "فاطمة آل مكتوم", "Nguyễn Văn", "Mañuel Muñoz", "Ἀθηνᾶ"]:
            line = encode_attr("cn", value)
            self.assertIn("cn:: ", line, msg=value)
            self.assertTrue(line.isascii())
            self.roundtrip(value)

    def test_folding_boundaries(self):
        for n in (75, 76, 77, 151, 152, 153, 400):
            self.roundtrip("x" * n)
        line = encode_attr("description", "y" * 200)
        physical = line.split("\n")
        self.assertEqual(len(physical[0]), 76)
        self.assertTrue(all(p.startswith(" ") for p in physical[1:]))

    def test_folded_base64_unfolds(self):
        self.roundtrip("刘" * 60)

    def test_dn_escaping(self):
        self.assertEqual(escape_dn_value("a,b"), "a\\,b")
        self.assertEqual(escape_dn_value("a+b"), "a\\+b")
        self.assertEqual(escape_dn_value("a\\b"), "a\\\\b")
        self.assertEqual(escape_dn_value('say "hi"'), 'say \\"hi\\"')
        self.assertEqual(escape_dn_value("#hash"), "\\#hash")
        self.assertEqual(escape_dn_value(" lead"), "\\ lead")
        self.assertEqual(escape_dn_value("trail "), "trail\\ ")
        self.assertEqual(escape_dn_value("mid dle"), "mid dle")
        self.assertEqual(make_dn([("uid", "au-14"), ("dc", "sigils")]), "uid=au-14,dc=sigils")

    def test_parser_reads_comments_and_base64(self):
        text = "# note\nversion: 1\n\ndn: cn=x\ncn:: " + base64.b64encode("刘".encode()).decode() + "\n\n"
        entries = parse_ldif(text)
        self.assertEqual(entries, [[("dn", "cn=x"), ("cn", "刘")]])


class BaseDnTests(unittest.TestCase):
    def test_accepts_dc_components(self):
        self.assertEqual(gen.parse_base("dc=sigils,dc=test"), [("dc", "sigils"), ("dc", "test")])

    def test_rejects_other_components(self):
        for bad in ["ou=people,dc=x", "dc=", "", "sigils"]:
            with self.assertRaises(ValueError, msg=bad):
                gen.parse_base(bad)


def synthetic(**overrides):
    rec = {
        "id": "xx-01", "country": "XX", "sex": "female", "age": 30, "name": "Ana Lopez",
        "given_names": ["Ana"], "family_names": ["Lopez"], "naming_culture": "Hispanic",
        "document_sex": "F", "slot": "individual", "household": None,
        "appearance": {"heritage": "Hispanic"},
    }
    rec.update(overrides)
    return rec


def render_people(records):
    rdns = gen.parse_base(gen.DEFAULT_BASE)
    entries = [gen.person_entry(r, rdns, gen.DEFAULT_PORTRAITS) for r in records]
    text = gen.render(entries, ["test"])
    return parse_ldif(text)


class PersonEdgeCases(unittest.TestCase):
    def entry(self, **kw):
        (entry,) = render_people([synthetic(**kw)])
        return entry

    def values(self, entry, name):
        return [v for n, v in entry if n == name]

    def test_basic_mapping(self):
        e = self.entry()
        self.assertEqual(self.values(e, "uid"), ["xx-01"])
        self.assertEqual(self.values(e, "cn"), ["Ana Lopez"])
        self.assertEqual(self.values(e, "sn"), ["Lopez"])
        self.assertEqual(self.values(e, "givenName"), ["Ana"])
        self.assertEqual(self.values(e, "mail"), ["xx-01@sigils.test"])
        self.assertIn("age=30", self.values(e, "description"))
        self.assertIn("heritage=Hispanic", self.values(e, "description"))
        self.assertNotIn("userPassword", [n for n, _ in e])

    def test_surname_falls_back_to_patronymic_then_last_word(self):
        e = self.entry(name="Aisha Khan", given_names=["Aisha"], family_names=[], patronymic="Khan")
        self.assertEqual(self.values(e, "sn"), ["Khan"])
        e = self.entry(name="Pema Yangchen", given_names=["Pema", "Yangchen"], family_names=[], patronymic=None)
        self.assertEqual(self.values(e, "sn"), ["Yangchen"])
        self.assertEqual(self.values(e, "givenName"), ["Pema Yangchen"])

    def test_single_name_person_still_has_sn(self):
        e = self.entry(name="Rana", given_names=["Rana"], family_names=[])
        self.assertEqual(self.values(e, "sn"), ["Rana"])

    def test_no_given_name_omits_attribute(self):
        e = self.entry(given_names=[])
        self.assertEqual(self.values(e, "givenName"), [])

    def test_native_name_option(self):
        e = self.entry(name="Choo Do-hoon", native_name="추도훈")
        self.assertEqual(self.values(e, "cn;x-native"), ["추도훈"])
        self.assertEqual(self.values(e, "cn"), ["Choo Do-hoon"])
        self.assertNotIn("cn;x-native", [n for n, _ in self.entry(native_name=None)])
        self.assertNotIn("cn;x-native", [n for n, _ in self.entry(native_name="")])

    def test_names_with_apostrophes_hyphens_and_commas_are_values_not_dns(self):
        e = self.entry(name="Seán O'Brien-Smith, Jr.", family_names=["O'Brien-Smith, Jr."], given_names=["Seán"])
        self.assertEqual(self.values(e, "cn"), ["Seán O'Brien-Smith, Jr."])
        self.assertEqual(self.values(e, "sn"), ["O'Brien-Smith, Jr."])

    def test_leading_space_and_colon_in_name(self):
        e = self.entry(name=" :Odd", given_names=[], family_names=[])
        self.assertEqual(self.values(e, "cn"), [" :Odd"])

    def test_age_zero_and_maximum(self):
        self.assertIn("age=0", self.values(self.entry(age=0), "description"))
        self.assertIn("age=120", self.values(self.entry(age=120), "description"))

    def test_nonbinary_document_sex(self):
        e = self.entry(sex="male", document_sex="X")
        self.assertIn("document-sex=X", self.values(e, "description"))

    def test_household_membership_is_described(self):
        e = self.entry(household={"id": "xx-h1", "role": "mother"})
        self.assertIn("household=xx-h1 role=mother", self.values(e, "description"))

    def test_long_name_folds_and_roundtrips(self):
        name = "Maximiliano Alejandro Fernández de la Cruz Villanueva-Montenegro"
        e = self.entry(name=name)
        self.assertEqual(self.values(e, "cn"), [name])

    def test_appearance_heritage_falls_back_to_naming_culture(self):
        e = self.entry(appearance={})
        self.assertIn("heritage=Hispanic", self.values(e, "description"))


class HouseholdTests(unittest.TestCase):
    def test_group_lists_only_emitted_members(self):
        rdns = gen.parse_base(gen.DEFAULT_BASE)
        a = synthetic(id="xx-01", household={"id": "xx-h1", "role": "mother"})
        b = synthetic(id="xx-02", name="Bea Lopez", household={"id": "xx-h1", "role": "daughter"})
        groups = gen.household_entries([a], rdns)
        self.assertEqual(len(groups), 1)
        members = [v for n, v in groups[0][1] if n == "member"]
        self.assertEqual(members, [gen.make_dn([("uid", "xx-01"), ("ou", "XX"), ("ou", "people"), *rdns])])
        groups = gen.household_entries([a, b], rdns)
        self.assertEqual(len([v for n, v in groups[0][1] if n == "member"]), 2)


class RepositoryTests(unittest.TestCase):
    """Runs against the real records. Slow-ish: about a few seconds."""

    @classmethod
    def setUpClass(cls):
        cls.text, cls.stats = gen.generate()
        cls.entries = parse_ldif(cls.text)

    def test_deterministic_bytes(self):
        again, _ = gen.generate()
        self.assertEqual(hashlib.sha256(self.text.encode()).hexdigest(),
                         hashlib.sha256(again.encode()).hexdigest())

    def test_counts(self):
        self.assertEqual(self.stats["people"], 7276)
        self.assertEqual(self.stats["countries"], 198)
        persons = [e for e in self.entries if ("objectClass", "inetOrgPerson") in e]
        self.assertEqual(len(persons), 7276)

    def test_every_dn_is_unique(self):
        dns = [v for e in self.entries for n, v in e if n == "dn"]
        self.assertEqual(len(dns), len(set(dns)))

    def test_every_person_has_required_attributes(self):
        for e in self.entries:
            if ("objectClass", "inetOrgPerson") not in e:
                continue
            names = [n for n, _ in e]
            for required in ("uid", "cn", "sn", "mail", "labeledURI"):
                self.assertIn(required, names)

    def test_group_members_exist(self):
        dns = {v for e in self.entries for n, v in e if n == "dn"}
        for e in self.entries:
            if ("objectClass", "groupOfNames") in e:
                for n, v in e:
                    if n == "member":
                        self.assertIn(v, dns)

    def test_header_names_source_digest(self):
        digest = hashlib.sha256()
        for path in sorted((gen.DEFAULT_PEOPLE).glob("*.jsonl")):
            digest.update(path.read_bytes())
        self.assertIn(f"source: {digest.hexdigest()[:16]}", self.text)

    def test_filtered_run_only_has_those_countries(self):
        text, stats = gen.generate(countries=["AF", "bt"], limit=None)
        self.assertEqual(stats["countries"], 2)
        uids = [v for e in parse_ldif(text) for n, v in e if n == "dn" and v.startswith("uid=")]
        self.assertTrue(uids)
        self.assertTrue(all(",ou=AF," in u or ",ou=BT," in u for u in uids))

    def test_limit(self):
        _, stats = gen.generate(limit=25)
        self.assertEqual(stats["people"], 25)

    def test_unknown_country_is_refused(self):
        with self.assertRaises(SystemExit):
            gen.generate(countries=["ZZ"])


if __name__ == "__main__":
    unittest.main()
