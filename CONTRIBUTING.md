# Expanding the population

The cast is 198 countries × 20 people. It can grow in three directions, in
roughly this order of usefulness:

1. **Corrections** to people who are already here — a name that is wrong for its
   culture, a masculine surname form on a woman, a portrait that does not match
   its record. These are the most valuable contributions and the easiest to make.
2. **More people per country.** Twenty is enough to be plausible and not enough
   to be representative. A country can grow past `-20` as long as the composition
   rules below still hold for the first twenty.
3. **New territories.** The list covers the 193 UN members plus Palestine, the
   Holy See, Kosovo, Hong Kong and Taiwan — places that issue their own
   documents. If somewhere is missing that a real system would need to represent,
   say so.

Nothing here needs a GPU unless you want to render portraits yourself. A pull
request that adds well-written records alone is welcome; the portraits can be
rendered after it is merged.

## The shape of a country

One file, `people/<cc>.jsonl`, lowercase ISO 3166-1 alpha-2, one JSON object per
line, exactly twenty lines. IDs run `cc-01` to `cc-20` in file order with no gaps.

The twenty are not arbitrary. They are:

- **Eight individuals** — one woman and one man in each of the age bands
  **18–29, 30–44, 45–64, 65+**. This is what stops a cast from being entirely
  photogenic twenty-somethings.
- **Two households** of at least two people each, each with at least one adult.
  Members share a `household.id` of the form `cc-h1`, `cc-h2`.
- **The remainder as coverage** — `slot: "coverage"` — for whatever the country
  needs that the individuals and households did not cover: a minor, a second
  naming culture, a regional minority, a migrant community that is genuinely
  part of the place.

## A record

```jsonc
{
  "id": "np-04",
  "country": "NP",
  "sex": "male",                    // female | male
  "age": 37,
  "name": "Bikash Gurung",          // the common Latin-script form
  "given_names": ["Bikash"],
  "family_names": ["Gurung"],       // [] for a mononym
  "naming_culture": "Nepali Gurung",
  "document_sex": "M",              // F | M | X | O
  "slot": "individual",             // individual | household | coverage
  "household": null,                // or {"id": "np-h1", "role": "…"}
  "appearance": {
    "heritage": "Gurung",
    "skin": "medium",
    "hair_color": "black",
    "hair_style": "short straight",
    "build": "average",
    "facial_hair": "clean-shaven",  // optional
    "glasses": false,               // optional
    "headwear": "dhaka topi"        // optional
  },
  "review": {                       // see below — not boilerplate
    "plausibility": "…",
    "adversarial": "…"
  }
}
```

**`sex` is the person; `document_sex` is the paperwork.** They are separate
fields because in a great many jurisdictions they disagree, and a system that
conflates them fails on real users. `sex` drives the portrait and is `female` or
`male`; a non-binary or unspecified marker goes in `document_sex` as `X` or `O`.

**`name` must contain every part in `given_names` and `family_names`**,
diacritics included. The display name is what a UI reads; the parts are what
documents and email systems read, and they must agree.

**Headwear may cover the hair, never the face.** These are profile pictures. A
niqab, a burqa, a mask or a balaclava is rejected by the checker — not as a
judgement about the garment, but because a portrait that does not show a face is
useless for the one job it has.

## What makes a record good

The checker enforces structure. It cannot enforce the part that matters.

- **The name must be plausible for that culture and that generation.** Names go
  in and out of fashion. A name that is right for someone born in 1958 is often
  wrong for someone born in 2005, and a cast full of the former reads as a
  translation exercise.
- **Surname forms must agree with the person.** Slavic, Baltic and Icelandic
  naming among others inflect family names by sex. Getting this wrong is the most
  common single error in the existing cast, and it was caught by review rather
  than by any program.
- **No real people.** Not a sitting politician, not a founding president, not a
  footballer, not a novelist. Common names are fine and unavoidable; a *specific
  identifiable person* is not. Check before you write, not after.
- **Households should look like households**, not like four unrelated records
  that happen to share an id. Ages and roles need to make sense together.
- **Avoid the stereotype and avoid its overcorrection.** Not everyone in a
  country wears national dress; not nobody does either.

## The review field

Every record carries two notes, and they are checked for boilerplate — if a
dozen records open with the same words, the file is rejected.

- **`plausibility`** — why this name suits this person: its form, its culture, the
  generation it belongs to.
- **`adversarial`** — what you checked for and did not find. This is the
  famous-name check, written down. "No public figure matches" on its own is not a
  note; say which direction you looked.

Write them about that person. A note that would read identically under any name
is not a review, and the checker will say so.

## Before you open a pull request

```sh
python3 check.py               # the whole cast
python3 check.py people/np.jsonl
```

`check.py` is standard-library Python and takes a second. It checks ids,
required fields, name agreement, the composition of each country, uniqueness of
names and ids across the entire cast, and — when run over everything — that
every person has all three portraits and no portrait is orphaned.

A green run is necessary and not sufficient. Records are reviewed by a person
before merging, particularly the naming.

## Rendering portraits

Only needed if you want to supply the faces as well as the records.
[`comfyui/`](comfyui/) has the model, the graph, the exact sampler settings and
the two hardware traps worth knowing. The rules that matter:

- **The prompt is assembled from the record**, never written free-hand. The model
  has no content filter; fixed characteristics are the input-side control, and
  they are why this cast is safe to publish.
- **The seed comes from the person's id**, so a record always produces the same
  face, and a re-render is reproducible rather than a lottery.
- **Every file carries its provenance** — prompt, negative, seed, model, date,
  the IPTC `trainedAlgorithmicMedia` marker and the synthetic-person disclaimer,
  in XMP. A portrait that arrives without that packet will not be merged.
- Output is `1024×1024`, then `512` and `256`, all AVIF at quality 75.

## Withdrawing someone

If a portrait or a name should not be here — it resembles a real person, it
reads as something the record does not say, anything at all — open an issue.
It will be withdrawn first and discussed afterwards.
