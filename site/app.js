/* sigils people — the contact sheet.
   No framework and no build step: GitHub Pages serves these three files as they are.
   The whole index is filtered in the browser; a person's full record is fetched
   from their country's file only when someone opens them.

   Every user-facing string lives in STRINGS and reaches the page through
   `data-i18n`, so adding a language is adding a key set — but only `en` ships.
   A machine-translated Spanish was written and removed: a page about getting
   names right in 198 cultures cannot be fronted by a translation nobody read. */

(() => {
  "use strict";

  const PER_PAGE = 60;
  const INDEX = "people/index.json";
  const RECORDS = (cc) => `people/${cc.toLowerCase()}.jsonl`;
  const PORTRAIT = (size, id) => `portraits/${size}/${id}.avif`;
  const REPO = "https://github.com/ambravo/sigils-people";

  /* -- words ------------------------------------------------------------- */

  const STRINGS = {
    en: {
      skip: "Skip to the portraits",
      lede: "Nobody on this page exists. Twenty people from each of 198 countries and territories — a name, an age, a heritage and a face — generated to be used as placeholder people wherever real ones would be a liability.",
      people: "people", peopleLower: "people", countries: "countries",
      threeSizes: "three sizes each, AVIF", whatFor: "what this is for",
      search: "Search", searchPlaceholder: "name, native name or id — try “muñoz”, “刘”, or “np-”",
      country: "Country", anyCountry: "Anywhere",
      sex: "Sex", any: "Any", female: "Female", male: "Male",
      ageFrom: "Age from", ageTo: "to", clear: "Clear",
      noneFound: "Nobody matches that.", clearFilters: "Clear the filters",
      loadFailed: "The cast index did not load.", retry: "Try again",
      showing: (a, b, n) => `Showing ${a}–${b} of ${n.toLocaleString("en")}`,
      showingAll: (n) => `${n.toLocaleString("en")} ${n === 1 ? "person" : "people"}`,
      loading: "Loading the cast…",
      prev: "Previous", next: "Next", page: (n) => `Page ${n}`,
      aboutTitle: "What this is for",
      about1: "Every design, demo, test fixture and empty state needs people in it. Using real faces means consent you do not have, licences you did not buy, and a photograph of a real person standing in for something they never agreed to. Using the same four stock portraits makes everything look like the same product. This is the third option: a cast large enough to be plausible, consistent enough to be reusable, and owned by nobody.",
      madeTitle: "How they were made",
      made1: "Each person was written first — name, age, sex, naming culture, household and appearance — against per-country rules, then independently reviewed. The portrait comes second and is derived from the record: the prompt is assembled from fixed characteristics rather than free text, and the image seed comes from the person's ID, so the same record always produces the same face. Rendering ran locally on consumer hardware with RealVisXL.",
      provTitle: "Every file says what it is",
      prov1: "Each portrait carries an XMP packet naming the person, the country, the prompt, the seed, the model and the render date, marked with IPTC's trainedAlgorithmicMedia digital source type and a plain-words disclaimer. Strip the page away and the file still declares itself synthetic.",
      useTitle: "Using them",
      use1: "Portraits are at a predictable path, so you can build the URL yourself:",
      use2: "The record for anyone is in their country's file — people/ad.jsonl, one JSON object per line — and people/index.json holds all of them in a compact form for searching.",
      licTitle: "Licence",
      lic1: "Copyright © 2026 Ariel Bravo Ayala. Records and code are MIT; the portraits are CC BY 4.0, and credit is a condition of that licence rather than a courtesy. Credit “Portraits by Ariel Bravo Ayala — sigils-people — CC BY 4.0”, in a colophon or an about screen; every file carries that line in its own metadata. Not for impersonation, harassment, disinformation, or presenting these people as real.",
      fine: "These are not real people. They have no consent to give and no rights to assert, which is the point — but it also means any resemblance to a living person is coincidence, and using one to stand for someone real is a misuse.",
      partOf: "part of", noneReal: "none of them real",
      portrait: "Portrait", rawRecord: "The whole record", close: "Close",
      report: "Report a problem", livesAlone: "lives alone", glasses: "glasses",
      region: "Region", anywhere: "Anywhere", heritage: "Heritage", anyHeritage: "Any",
      wholeRegion: (r) => `All of ${r}`,
      notReal: "Not a real person. Generated, never photographed.",
      credit: "Portraits by Ariel Bravo Ayala · CC BY 4.0 · credit required",
      recordFailed: "That record could not be loaded.",
      f: { country: "Country", age: "Age", sex: "Sex", naming: "Naming culture",
           nativeName: "Written", patronymic: "Patronymic", region: "Region",
           heritage: "Heritage", household: "Household", appearance: "Appearance",
           documentSex: "Document sex", id: "Identifier" },
      years: (n) => `${n} years old`,
    },
  };

  // One language ships. The lookup stays indirect so a second is a data change.
  const lang = "en";
  const t = () => STRINGS[lang];

  /* -- state ------------------------------------------------------------- */

  const $ = (sel) => document.querySelector(sel);
  const el = {
    grid: $("#grid"), result: $("#result"), pager: $("#pager"),
    empty: $("#empty"), failed: $("#failed"),
    q: $("#q"), region: $("#region"), country: $("#country"), heritage: $("#heritage"),
    sex: $("#sex"), amin: $("#amin"), amax: $("#amax"),
    dialog: $("#person"),
  };

  let all = [];          // {id, country, name, sex, age, heritage, hay}
  let countries = {};
  let matches = [];
  let page = 1;
  const recordCache = new Map();

  const fold = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

  /* -- url --------------------------------------------------------------- */

  function readUrl() {
    const p = new URLSearchParams(location.hash.slice(1));
    el.q.value = p.get("q") || "";
    el.region.value = p.get("r") || "";
    fillCountries();
    el.country.value = p.get("c") || "";
    el.heritage.value = p.get("h") || "";
    el.sex.value = p.get("s") || "";
    el.amin.value = p.get("from") || "";
    el.amax.value = p.get("to") || "";
    page = Math.max(1, parseInt(p.get("p") || "1", 10) || 1);
    return p.get("id");
  }

  function writeUrl(id) {
    const p = new URLSearchParams();
    if (el.q.value.trim()) p.set("q", el.q.value.trim());
    if (el.region.value) p.set("r", el.region.value);
    if (el.country.value) p.set("c", el.country.value);
    if (el.heritage.value) p.set("h", el.heritage.value);
    if (el.sex.value) p.set("s", el.sex.value);
    if (el.amin.value) p.set("from", el.amin.value);
    if (el.amax.value) p.set("to", el.amax.value);
    if (page > 1) p.set("p", String(page));
    if (id) p.set("id", id);
    const hash = p.toString();
    const url = hash ? `#${hash}` : location.pathname + location.search;
    history.replaceState(null, "", url);
  }

  /* -- filtering --------------------------------------------------------- */

  // "r:Africa" is a whole region, "s:Northern Africa" one subregion inside it.
  function inRegion(p, value) {
    if (!value) return true;
    const c = countries[p.country];
    if (!c) return false;
    const [kind, name] = [value.slice(0, 1), value.slice(2)];
    return kind === "r" ? c.region === name : c.subregion === name;
  }

  function filter() {
    const q = fold(el.q.value.trim());
    const r = el.region.value;
    const c = el.country.value;
    const h = el.heritage.value;
    const s = el.sex.value;
    const lo = el.amin.value === "" ? -Infinity : Number(el.amin.value);
    const hi = el.amax.value === "" ? Infinity : Number(el.amax.value);
    matches = all.filter((p) =>
      (!q || p.hay.includes(q)) &&
      inRegion(p, r) &&
      (!c || p.country === c) &&
      (!h || p.heritage === h) &&
      (!s || p.sex === s) &&
      p.age >= lo && p.age <= hi);
  }

  /* -- rendering --------------------------------------------------------- */

  function render() {
    const pages = Math.max(1, Math.ceil(matches.length / PER_PAGE));
    if (page > pages) page = pages;
    const from = (page - 1) * PER_PAGE;
    const slice = matches.slice(from, from + PER_PAGE);

    el.grid.setAttribute("aria-busy", "false");
    el.failed.hidden = true;
    el.empty.hidden = matches.length > 0;
    el.grid.hidden = matches.length === 0;
    el.pager.hidden = pages < 2;

    el.result.textContent = matches.length === 0
      ? ""
      : (pages < 2 ? t().showingAll(matches.length)
                   : t().showing(from + 1, from + slice.length, matches.length));

    const frag = document.createDocumentFragment();
    for (const p of slice) {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "cell";
      cell.dataset.id = p.id;
      const cc = countries[p.country];
      const img = document.createElement("img");
      img.src = PORTRAIT("s", p.id);
      img.width = 256; img.height = 256;
      img.loading = "lazy"; img.decoding = "async";
      img.alt = `${p.name}, ${t().years(p.age)}, ${cc ? cc.name : p.country}`;
      const cap = document.createElement("figcaption");
      const id = document.createElement("span"); id.className = "id"; id.textContent = p.id;
      const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = p.name;
      cap.append(id, nm);
      if (p.native) {
        const nat = document.createElement("span");
        nat.className = "nat"; nat.lang = ""; nat.textContent = p.native;
        cap.append(nat);
      }
      cell.append(img, cap);
      frag.append(cell);
    }
    el.grid.replaceChildren(frag);
    renderPager(pages);
  }

  function renderPager(pages) {
    if (pages < 2) { el.pager.replaceChildren(); return; }
    const frag = document.createDocumentFragment();
    const btn = (label, target, opts = {}) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = label;
      if (opts.label) b.setAttribute("aria-label", opts.label);
      if (opts.current) b.setAttribute("aria-current", "page");
      b.disabled = !!opts.disabled;
      if (!opts.disabled) b.addEventListener("click", () => go(target));
      return b;
    };
    frag.append(btn("‹", page - 1, { disabled: page === 1, label: t().prev }));

    // First, last, and a window of three around where you are.
    const want = new Set([1, pages, page - 1, page, page + 1]);
    const shown = [...want].filter((n) => n >= 1 && n <= pages).sort((a, b) => a - b);
    let last = 0;
    for (const n of shown) {
      if (n - last > 1) {
        const gap = document.createElement("span");
        gap.className = "gap"; gap.textContent = "…"; gap.setAttribute("aria-hidden", "true");
        frag.append(gap);
      }
      frag.append(btn(String(n), n, { current: n === page, label: t().page(n) }));
      last = n;
    }
    frag.append(btn("›", page + 1, { disabled: page === pages, label: t().next }));
    el.pager.replaceChildren(frag);
  }

  function go(n) {
    page = n;
    writeUrl();
    render();
    document.getElementById("sheet").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function apply(resetPage = true) {
    if (resetPage) page = 1;
    filter();
    writeUrl();
    render();
  }

  /* -- one person -------------------------------------------------------- */

  async function recordsFor(cc) {
    if (recordCache.has(cc)) return recordCache.get(cc);
    const res = await fetch(RECORDS(cc));
    if (!res.ok) throw new Error(`${res.status}`);
    const map = new Map();
    for (const line of (await res.text()).split("\n")) {
      if (!line.trim()) continue;
      const r = JSON.parse(line);
      map.set(r.id, r);
    }
    recordCache.set(cc, map);
    return map;
  }

  function household(r) {
    // {id, role} for the 1,374 people who live with someone, null for the rest.
    const h = r.household;
    if (h && typeof h === "object") {
      return h.role ? `${h.role} · ${h.id}` : String(h.id || "");
    }
    return r.slot === "individual" ? t().livesAlone : "";
  }

  function reportUrl(id, rec) {
    // Pre-filled so a report arrives with the person already identified — the
    // wrong name or the wrong face is useless to act on without the id.
    const title = `${id}${rec ? ` (${rec.name})` : ""}: `;
    const body = [
      "<!-- What is wrong? A name that is wrong for its culture, a portrait that",
      "does not match the record, a resemblance to a real person, anything else. -->",
      "",
      "",
      "---",
      `Person: \`${id}\``,
      rec ? `Name: ${rec.name}` : "",
      rec ? `Country: ${rec.country} · Naming culture: ${rec.naming_culture}` : "",
      `Portrait: ${new URL(PORTRAIT("m", id), location.href).href}`,
    ].filter(Boolean).join("\n");
    return `${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
  }

  function facts(r) {
    const s = t(), a = r.appearance || {};
    const cc = countries[r.country];
    const look = [
      a.skin,
      a.hair_color && a.hair_style ? `${a.hair_style} ${a.hair_color} hair` : a.hair_color,
      a.build,
      a.facial_hair,
      a.headwear,
      a.glasses ? s.glasses : "",
    ].filter(Boolean).join(", ");
    return [
      [s.f.id, r.id, true],
      [s.f.nativeName, r.native_name],
      [s.f.patronymic, r.patronymic],
      [s.f.country, cc ? `${cc.name} (${r.country})` : r.country],
      [s.f.age, s.years(r.age)],
      [s.f.sex, s[r.sex] || r.sex],
      [s.f.naming, r.naming_culture],
      [s.f.documentSex, r.document_sex],
      [s.f.heritage, a.heritage],
      [s.f.household, household(r)],
      [s.f.appearance, look],
    ].filter(([, v]) => v);
  }

  async function open(id) {
    const cc = id.split("-")[0];
    const img = $("#person-img");
    $("#person-id").textContent = id;
    $("#person-name").textContent = "";
    $("#person-facts").replaceChildren();
    $("#person-json").textContent = "";
    img.src = PORTRAIT("m", id);
    img.alt = "";
    for (const [k, size] of [["dl-s", "s"], ["dl-m", "m"], ["dl-l", "l"]]) {
      $(`#${k}`).href = PORTRAIT(size, id);
    }
    $("#report").href = reportUrl(id, null);
    if (!el.dialog.open) el.dialog.showModal();
    writeUrl(id);

    try {
      const rec = (await recordsFor(cc)).get(id);
      if (!rec) throw new Error("not in its country file");
      $("#person-name").textContent = rec.name;
      img.alt = `${rec.name}, ${t().years(rec.age)}`;
      const dl = document.createDocumentFragment();
      for (const [k, v] of facts(rec)) {
        const dt = document.createElement("dt"); dt.textContent = k;
        const dd = document.createElement("dd"); dd.textContent = v;
        if (k === t().f.id) dd.className = "mono";
        dl.append(dt, dd);
      }
      $("#person-facts").replaceChildren(dl);
      $("#person-json").textContent = JSON.stringify(rec, null, 2);
      $("#report").href = reportUrl(id, rec);
    } catch {
      $("#person-name").textContent = t().recordFailed;
    }
  }

  function close() {
    if (el.dialog.open) el.dialog.close();
    writeUrl();
  }

  /* -- language ---------------------------------------------------------- */

  // One control, both granularities: a whole region, or a subregion inside it.
  function fillRegions() {
    const s = t();
    const keep = el.region.value;
    const tree = new Map();
    for (const c of Object.values(countries)) {
      if (!tree.has(c.region)) tree.set(c.region, new Map());
      const subs = tree.get(c.region);
      subs.set(c.subregion, (subs.get(c.subregion) || 0) + c.count);
    }
    const frag = document.createDocumentFragment();
    frag.append(new Option(s.anywhere, ""));
    for (const [region, subs] of [...tree].sort((a, b) => a[0].localeCompare(b[0]))) {
      const group = document.createElement("optgroup");
      group.label = region;
      const whole = [...subs.values()].reduce((a, b) => a + b, 0);
      group.append(new Option(`${s.wholeRegion(region)} (${whole})`, `r:${region}`));
      for (const [sub, n] of [...subs].sort((a, b) => a[0].localeCompare(b[0]))) {
        group.append(new Option(`${sub} (${n})`, `s:${sub}`));
      }
      frag.append(group);
    }
    el.region.replaceChildren(frag);
    el.region.value = keep;
  }

  // The country list follows the region, so the two controls cannot disagree.
  function fillCountries() {
    const s = t();
    const keep = el.country.value;
    const region = el.region.value;
    const opts = [new Option(s.anyCountry, "")];
    for (const [code, c] of Object.entries(countries)) {
      if (region && !inRegion({ country: code }, region)) continue;
      opts.push(new Option(`${c.name} (${c.count})`, code));
    }
    el.country.replaceChildren(...opts);
    // Keep the choice only if it still exists under this region.
    el.country.value = [...el.country.options].some((o) => o.value === keep) ? keep : "";
  }

  function fillHeritages() {
    const s = t();
    const keep = el.heritage.value;
    const counts = new Map();
    for (const p of all) {
      if (p.heritage) counts.set(p.heritage, (counts.get(p.heritage) || 0) + 1);
    }
    const opts = [new Option(s.anyHeritage, "")];
    for (const [h, n] of [...counts].sort((a, b) => a[0].localeCompare(b[0]))) {
      opts.push(new Option(`${h} (${n})`, h));
    }
    el.heritage.replaceChildren(...opts);
    el.heritage.value = [...el.heritage.options].some((o) => o.value === keep) ? keep : "";
  }

  function paint() {
    const s = t();
    document.documentElement.lang = lang;
    document.documentElement.dataset.lang = lang;
    for (const node of document.querySelectorAll("[data-i18n]")) {
      const v = s[node.dataset.i18n];
      if (typeof v === "string") node.textContent = v;
    }
    for (const node of document.querySelectorAll("[data-i18n-ph]")) {
      const v = s[node.dataset.i18nPh];
      if (typeof v === "string") node.placeholder = v;
    }
    for (const node of document.querySelectorAll("[data-i18n-aria]")) {
      const v = s[node.dataset.i18nAria];
      if (typeof v === "string") node.setAttribute("aria-label", v);
    }
    // Grouping differs by locale, so the counts are re-formatted, not just re-labelled.
    for (const n of document.querySelectorAll('[data-count="people"]')) {
      n.textContent = all.length.toLocaleString(lang);
    }
    for (const n of document.querySelectorAll('[data-count="countries"]')) {
      n.textContent = Object.keys(countries).length.toLocaleString(lang);
    }
    fillRegions();
    fillCountries();
    fillHeritages();
    el.sex.options[0].textContent = s.any;
    el.sex.options[1].textContent = s.female;
    el.sex.options[2].textContent = s.male;
  }

  /* -- start ------------------------------------------------------------- */

  async function start() {
    el.result.textContent = t().loading;
    try {
      const [idx, ctry] = await Promise.all([
        fetch(INDEX).then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); }),
        fetch("people/countries.json").then((r) => (r.ok ? r.json() : {})),
      ]);
      countries = ctry;
      const f = idx.fields;
      const at = (row, name) => row[f.indexOf(name)];
      all = idx.people.map((row) => {
        const p = {
          id: at(row, "id"), country: at(row, "country"), name: at(row, "name"),
          native: at(row, "native") || "", sex: at(row, "sex"), age: at(row, "age"),
          heritage: at(row, "heritage"),
        };
        // The native name goes in unfolded: stripping combining marks is a Latin
        // idea, and it would mangle scripts that build characters out of them.
        p.hay = fold(`${p.name} ${p.id} ${p.heritage}`) + " " + p.native;
        return p;
      });
      paint();
      const openId = readUrl();
      filter();
      render();
      if (openId) open(openId);
    } catch {
      el.grid.setAttribute("aria-busy", "false");
      el.grid.hidden = true;
      el.result.textContent = "";
      el.failed.hidden = false;
    }
  }

  /* -- wiring ------------------------------------------------------------ */

  let debounce;
  el.q.addEventListener("input", () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => apply(), 120);
  });
  el.region.addEventListener("change", () => {
    fillCountries();
    apply();
  });
  for (const node of [el.country, el.heritage, el.sex, el.amin, el.amax]) {
    node.addEventListener("change", () => apply());
  }
  $("#filters").addEventListener("submit", (e) => e.preventDefault());

  const clearAll = () => {
    el.q.value = ""; el.region.value = ""; el.country.value = "";
    el.heritage.value = ""; el.sex.value = "";
    el.amin.value = ""; el.amax.value = "";
    fillCountries();
    apply();
  };
  $("#clear").addEventListener("click", clearAll);
  $("#empty-clear").addEventListener("click", clearAll);
  $("#retry").addEventListener("click", () => {
    el.failed.hidden = true;
    el.grid.hidden = false;
    el.grid.setAttribute("aria-busy", "true");
    start();
  });

  el.grid.addEventListener("click", (e) => {
    const cell = e.target.closest(".cell");
    if (cell) open(cell.dataset.id);
  });

  $("#close").addEventListener("click", close);
  el.dialog.addEventListener("close", () => writeUrl());
  el.dialog.addEventListener("click", (e) => {
    // A click on the backdrop lands on the dialog itself, never on its contents.
    if (e.target === el.dialog) close();
  });

  start();
})();
