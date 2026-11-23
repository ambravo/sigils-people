# LDAP import

`generate_ldif.py` turns the cast in `people/*.jsonl` into an LDIF file that an
LDAP directory can import. It is pure Python with no dependencies, and its output
is byte-identical on every run for the same records and options.

```bash
python3 tools/ldap/generate_ldif.py -o cast.ldif          # the whole cast
python3 tools/ldap/generate_ldif.py --country AF --country BT --limit 40 > sample.ldif
python3 -m unittest discover -s tools/ldap -v              # tests
```

The generated file is not committed. It is about 4 MB and comes straight from the
records, so the same command rebuilds it.

## Layout

| DN | Object class | Holds |
| --- | --- | --- |
| `dc=sigils,dc=test` | dcObject, organization | the base |
| `ou=people,<base>` | organizationalUnit | everyone |
| `ou=<CC>,ou=people,<base>` | organizationalUnit | one per country, `description` = name |
| `uid=<id>,ou=<CC>,ou=people,<base>` | inetOrgPerson | one per person |
| `cn=<household>,ou=<CC>,ou=people,<base>` | groupOfNames | one per household, `member` = the people in it |

Use `--base-dn` for another suffix. Only `dc=` components are accepted.

## Attribute mapping

| LDAP | From the record | Note |
| --- | --- | --- |
| `uid`, `cn`, `displayName` | `id`, `name`, `name` | `cn` is the full name |
| `givenName` | `given_names` joined by spaces | omitted when empty |
| `sn` | `family_names`, else `patronymic`, else last word of `name` | `sn` is required, so it is never empty |
| `cn;x-native` | `native_name` | only for people who have one |
| `mail` | `<id>@sigils.test` | `.test` is reserved; no mail is ever delivered |
| `labeledURI` | portrait URL, `portraits/m/<id>.avif` | `--portraits` changes the prefix |
| `description` | `age=`, `sex=`, `document-sex=`, `heritage=`, `naming-culture=`, `patronymic=`, `household=<id> role=<role>` | `inetOrgPerson` has no field for these, so they are text |

No `userPassword` is written. Set passwords at load time, not in the file.

## Decisions

- **Why `sn` falls back.** 201 records have no `family_names`. Afghan and
  Bhutanese names are patronymic or given-name only, so the patronymic is used
  when it exists. For the rest, the last word of the name is used.
- **Why `description` for age and sex.** Those have no standard `inetOrgPerson`
  attribute. A custom schema would be more precise but needs the directory to
  load it first, which breaks the "any LDAP server" goal.
- **Why every non-ASCII value is base64.** RFC 2849 does not allow raw UTF-8 in
  a plain LDIF value, so `刘备` and `فاطمة` are written as `attr:: <base64>`. Any
  LDIF reader decodes them.
- **Why households are groups.** Members of one household share a country, so each
  group sits under its country's OU.

## Checks

- `tools/ldap/ldif.py` implements the encoding and a parser; the tests check round
  trips, folding at 76 characters, DN escaping, and every edge case in
  `test_ldif.py` (leading space or colon, trailing space, empty values, NUL, long
  names, native names, missing family names, households cut by `--limit`).
- The repository tests check counts (7,276 people, 198 countries, 396 households),
  unique DNs, required attributes, and that every group member exists.
- OpenLDAP's own parser accepts the whole output: `ldapadd -n -f cast.ldif` reads
  all 7,872 entries without an error. That is a dry run and needs no server.
