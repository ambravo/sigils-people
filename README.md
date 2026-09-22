# sigils people

**3,960 people who do not exist.** Twenty from each of 198 countries and
territories, each with a written record and a photographic portrait in three
sizes. Free to use, openly licensed, generated on consumer hardware, and marked
in every file as synthetic.

**[Browse them →](https://ambravo.github.io/sigils-people/)**

---

## What is in here

```
people/<cc>.jsonl      the records — one JSON object per line, 20 per country
people/index.json      all 3,960 in a compact form, for searching
people/countries.json  country code → name, count, region and subregion
portraits/s/<id>.avif    256 px
portraits/m/<id>.avif    512 px
portraits/l/<id>.avif   1024 px
comfyui/               the model, the graph and the settings that made them
```

An ID is the lowercase ISO country code, a hyphen, and a two-digit number:
`ad-01`, `np-04`, `br-17`. That is the only key you need — the portrait paths and
the record are all derived from it.

Names carry their diacritics, and the 1,241 people from places that do not write
in the Latin alphabet carry their name in their own script as well:

```jsonc
{
  "id": "cn-04",
  "name": "Liu Tao",
  "native_name": "刘涛",
  "naming_culture": "Han Chinese",
  …
}
```

A full record:

```jsonc
{
  "id": "ad-01",
  "country": "AD",
  "sex": "female",
  "age": 24,
  "name": "Maria Gali",
  "given_names": ["Maria"],
  "family_names": ["Gali"],
  "naming_culture": "Andorran Catalan",
  "document_sex": "F",
  "slot": "individual",
  "household": null,
  "appearance": {
    "heritage": "Andorran Catalan",
    "skin": "fair",
    "hair_color": "brown",
    "hair_style": "shoulder-length",
    "build": "slim"
  }
}
```

## Using them

Build the URL yourself; there is no API to call.

```html
<img src="https://ambravo.github.io/sigils-people/portraits/m/np-04.avif"
     alt="Bikash Gurung" width="512" height="512">
```

AVIF renders in every current browser in an ordinary `<img>` tag — Chrome 85,
Firefox 93, Safari 16.4, Edge 121 — at about 95% of installed browsers, and it
is roughly a third the size of the equivalent JPEG.

For anything beyond a demo, **serve them yourself** rather than hotlinking a
GitHub Pages site. Two ways, both free:

```sh
# a container that serves them with the right headers
docker run --rm -p 8080:80 ghcr.io/ambravo/sigils-people:serve

# or take just the files into your own image
COPY --from=ghcr.io/ambravo/sigils-people:data /portraits /srv/portraits
```

The `data` image is `FROM scratch` — the files and nothing else, ordered so that
the portraits sit in their own layer. Pull it once and later versions that only
change records or the site cost you kilobytes.

## Every file says what it is

Each portrait carries an XMP packet with the **whole record** — name, native
name, patronymic, given and family names, naming culture, country, age, sex,
document sex, heritage, household and role, and every recorded detail of
appearance — alongside the exact prompt and negative, the seed, the model and the
render date, marked with IPTC's `trainedAlgorithmicMedia` digital source type,
`xmpRights` licence terms, and a plain-words disclaimer.

```sh
exiftool -DigitalSourceType -Identifier -Seed -Model portraits/l/np-04.avif
```

Strip this repository away and the file still declares itself synthetic. That is
deliberate: a synthetic face that has lost its provenance is exactly the thing
everyone is worried about.

## How they were made

Each person was **written first** — name, age, sex, naming culture, household and
appearance, against per-country rules — and reviewed independently before any
image existed. The portrait is derived from the record: the prompt is assembled
from fixed characteristics rather than free text, and the seed comes from the
person's ID, so a record always produces the same face.

Rendering was RealVisXL V5.0 Lightning through ComfyUI on an Apple M4 with 16 GB
of unified memory, about 70 seconds a portrait, roughly 78 hours for the cast.
[`comfyui/`](comfyui/) has the graph, the settings, the measurements behind the
model choice, and how to reproduce any single portrait exactly.

## Running the gallery locally

```sh
./serve.sh          # http://localhost:8000
```

No build step and no dependencies beyond Python 3. The repository root *is* the
site.

## Licence

Copyright © 2026 Ariel Bravo Ayala.

| | |
|---|---|
| Records, code, the site | **MIT** — [LICENSE](LICENSE) |
| Portraits | **CC BY 4.0 — credit required** — [LICENSE-PORTRAITS](LICENSE-PORTRAITS) |

Use them freely, including commercially. **Credit is a condition of the licence,
not a courtesy.** Reproduce this, or something carrying the same four things:

> Portraits by [Ariel Bravo Ayala](https://github.com/ambravo/sigils-people) —
> sigils-people — [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
> Synthetic people; not photographs of anyone.

It can live in a colophon, credits page or about screen — it does not have to sit
on each image. Every portrait already carries the creator, the notice and the
exact credit line in its own metadata, so you never have to come back here to
find out who to name:

```sh
exiftool -Creator -Rights -Attribution -Copyright portraits/l/np-04.avif
```

The model that produced these, RealVisXL under CreativeML Open RAIL++-M, claims
no rights in its output — so the CC BY grant is mine to make, and mine to
condition on credit. That licence's use restrictions are carried forward anyway,
as terms of this dataset rather than an inherited obligation: no impersonation,
harassment, disinformation, or presenting these people as real. The full list is
in [LICENSE-PORTRAITS](LICENSE-PORTRAITS).

## These are not real people

They have no consent to give and no rights to assert, which is the point. It also
means any resemblance to a living person is coincidence, and using one to stand
for someone real is a misuse — not a clever shortcut.

Found a portrait that should not be here, or a name that belongs to someone real?
[Open an issue](https://github.com/ambravo/sigils-people/issues). It will be
withdrawn, not argued about.

---

Part of [sigils](https://github.com/ambravo/sigils), an avatar service.
Contributions — new countries, more people per country, corrections — are
welcome: see [CONTRIBUTING.md](CONTRIBUTING.md).
