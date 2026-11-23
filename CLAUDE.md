# sigils-people — rules for working in this repository

## Keep only the latest state

This repository keeps one commit: the current state. After every change, squash
the history so `main` holds a single commit and nothing else:

```bash
tools/squash.sh "Message describing the change"
```

The script commits the working tree as an orphan commit, force-pushes `main`,
deletes every other branch on origin and locally, expires the reflog, gc's,
then dispatches the `pages` and `image` workflows by hand. It is the only way
this repository's history is changed; do not keep older commits "for reference".

Why: the portraits are about 1.2 GB and every regeneration adds a full copy to
history. A single commit is the only thing that keeps the repo near a size
GitHub can host.

## Before squashing

1. `python3 tools/normalize_metadata.py --write` if records changed (spelling only).
2. `python3 tools/build_index.py` so `people/index.json` matches the records.
3. `python3 tools/sync_xmp.py --write` if any record field changed, so the
   portraits' XMP matches (needs exiftool). Only record fields are rewritten; the
   rendered prompt, seed, model and render key are never changed.
4. `python3 check.py` must pass.
5. `python3 -m unittest discover -s tools/ldap` must pass if anything under
   `tools/ldap/` or any record changed. The LDIF is generated on demand and is
   never committed.

## Record rules

- Records are one JSON object per line; `json.dumps(..., ensure_ascii=False)`
  reproduces each line exactly, and the normaliser relies on that.
- A spelling variant (case, space vs hyphen vs underscore) of the same
  heritage, naming culture or appearance value is an error; `check.py` fails on it.
- Synonyms (grey/gray, hijab/headscarf) are not changed automatically.
