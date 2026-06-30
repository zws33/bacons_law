# Wikidata Exploration — findings & access-path reasoning

> Pre-build reconnaissance for the Phase 1 ETL (the bipartite movie↔actor graph). This is a
> **characterization** of the Wikidata source — what shape the data is and whether it's fit for
> purpose — not the extract itself. Captured 2026-06-30. Numbers are point-in-time (Wikidata changes
> daily); re-run the queries to refresh.

---

## 1. Why this exists

Before designing the extract stage we needed to answer five decision-driving questions against the
real data, not assumptions:

| Decision | Question | Answered in |
|----------|----------|-------------|
| Catalog threshold | Where do we cut for ~50–100k "notable" films? | §3 |
| Format / scale | Does the graph fit in RAM (does scale even matter)? | §3 |
| Min-cast floor | Is the cast data usable, or thin? | §3 |
| Cast-depth cap | Can we implement "top-N **billed**"? | §3 |
| Recognizability | Is "notable" actually *recognizable* to players? | §3 |

The headline outcomes that **edited the plan**: billing order is effectively absent (kills "top-N
billed"), and sitelink count alone is language-agnostic (a recognizability problem the counts hid).

---

## 2. How to reproduce

- **Endpoint:** `https://query.wikidata.org/sparql` (SPARQL over HTTP). Interactive GUI:
  <https://query.wikidata.org> — use this for exploration (autocomplete, examples, query-time display).
- **Etiquette / hard rules:**
  - A descriptive `User-Agent` with contact info is **required** (generic/absent agents are blocked).
  - WDQS enforces a **hard ~60s server timeout** → `"upstream request timeout"`.
- **Reproducible invocation** (query kept in a file to avoid shell-quoting issues):

  ```bash
  curl -s -G "https://query.wikidata.org/sparql" \
    -H "User-Agent: bacons-law-etl-exploration/0.1 (zach.smith33@gmail.com)" \
    -H "Accept: application/sparql-results+json" \
    --data-urlencode query@query.rq \
    --max-time 58            # client timeout, just under WDQS's 60s server limit
  ```

### Data-model primer (for future readers)

Wikidata is a labeled multigraph where **edges can carry attributes**:

- **Items** = QIDs (`Q11424` = "film"); **properties** = PIDs (`P31` instance-of, `P161` cast member,
  `P577` publication date, `P1545` series ordinal).
- A **statement** is `item — property — value`. A statement can have **qualifiers** (attributes on the
  edge, e.g. `P1545` billing position on a cast-member statement).
- **Sitelinks** = Wikipedia articles per language; their *count* is a notability proxy.

SPARQL exposes the same fact at two depths — **this distinction explains every timeout below:**

```sparql
?film wdt:P161 ?actor .   # TRUTHY: one materialized hop. FAST.
# vs.
?film p:P161 ?stmt .      # STATEMENT node (reified) ...
?stmt pq:P1545 ?ord .     #   ... then the qualifier. SLOW — times out at scale.
```

Prefix cheat-sheet (WDQS predefines these): `wd:` entity · `wdt:` truthy property · `p:` →statement ·
`ps:` statement→value · `pq:` statement→qualifier · `wikibase:` ontology (incl. the materialized
`wikibase:sitelinks` count and the label service) · `schema:` sitelinks/articles.

**Rule of thumb:** stay on truthy `wdt:` unless you genuinely need qualifiers/ranks/references — those
are exactly the queries that won't scale interactively.

---

## 3. Findings (2026-06-30)

### Notability distribution — all films (`P31 = Q11424`)

| sitelinks | films in band | **cumulative ≥** |
|-----------|--------------:|-----------------:|
| 1 | 146,212 | 346,587 |
| 2–4 | 132,797 | 200,375 |
| 5–9 | 42,795 | **67,578** |
| 10–19 | 15,926 | 24,783 |
| 20–49 | 8,021 | 8,857 |
| 50+ | 836 | 836 |

~346,600 films total. **≥5 sitelinks → 67,578** lands in the case study's 50–100k target. ≥2 explodes
to 200k (mostly obscure); ≥10 trims to ~25k (leaner, harder game).

### Cast completeness — films ≥5 sitelinks

| cast size | films |
|-----------|------:|
| 0 (no `P161`) | ~6,400 (= 67,578 − 61,221) |
| 1–2 | 10,111 |
| 3–9 | 26,934 |
| 10+ | 24,176 |

Films with a **usable** cast list (≥3) ≈ **51,100** — the *real* catalog size at ≥5. ~25% of "notable"
films have <3 cast → **a min-cast floor (≥3) is needed**; the notability filter alone is insufficient.

### Edge volume & cast size

- Raw cast edges, films ≥5: **592,682** (≡ 593,403 cast statements — one statement per edge).
- Average cast/film: **~10** (≥5), **~25** (≥50). The cap mainly bites blockbusters.
- → **Scale is a non-issue.** ~600k edges is tens of MB. This de-risks the format choice (JSON is
  fine) and means the cap's job is **gameplay + policy**, not size.

### Billing order (`P1545`) coverage — the decisive finding

Among the **836 most-notable films** (≥50 sitelinks): **1,579 / 20,663 = 7.6%** of cast statements
carry `P1545`. That's the *optimistic ceiling* (best-curated films); the broader ≥5 catalog is lower.

→ **Billing order is effectively absent on Wikidata.** "Top-N **billed**" is not implementable from
ordinals. The "fallback" becomes the **primary** mechanism: rank a film's cast by the **actor's own
sitelink count** and take top-N. (This reuses a signal we already pull and tames super-connector
blockbusters — the gameplay knob.)

### Recognizability — qualitative spot-check

Films at *exactly* 5 sitelinks are clearly marginal and **heavily non-English** (German, Italian,
Scandinavian, older/niche). Counts hid this; eyeballing rows exposed it.

→ Sitelink count is **language-agnostic** notability. For an English-speaking audience, prefer an
**English-Wikipedia anchor**: 160,826 films have an enwiki article — broad on its own, so use the
**intersection** `enwiki ∩ ≥N sitelinks ∩ ≥3 cast`.

---

## 4. Design conclusions for the ETL

1. **Filter = notability signal + min-cast floor (shape matters more than the exact number).**
   - Notability: lean **enwiki ∩ ≥5 sitelinks** (recognizable *and* globally notable) over raw count.
   - Min-cast floor: **≥3** (drops ~25% dead-weight films).
   - Treat the exact threshold as a **playtest-tuning dial** — a one-line filter change + re-run.
2. **Cap by actor notability, not billing order** (ordinals are ~8% — unusable). Rank cast by actor
   sitelink count, take top-N. `P1545` is at most a rare tiebreaker.
3. **Build the capped edge list once, index both directions** (`movie→actors`, `actor→movies`) so the
   graph can never be asymmetric.
4. **Movies only:** exclude documentary (`Q93204`) and TV-movie (`Q506240`) types at extract
   (per project constraint; not yet measured here).
5. **Artifact keys = Wikidata QIDs** (stable, provenance-inline); the engine's eventual ID type is a
   loader-side concern (see decision to keep `:core`'s shape open).

---

## 5. Access-path reasoning

Three ways to get Wikidata data; route work by job, not habit:

| Path | What it's for | Verdict here |
|------|---------------|--------------|
| **WDQS / SPARQL** (`query.wikidata.org/sparql`) | Graph queries, aggregates, relationships | **Exploration ✓** (this doc). Bad for *bulk* extraction — the 60s wall. |
| **MediaWiki Action API** (`wikidata.org/w/api.php`, `wbgetentities`) | Fetch full entity JSON by QID over REST | Candidate for **entity detail** once the QID list is known. |
| **Dumps** | Whole graph offline | Completeness/reproducibility at the cost of size; deferred. |

**Concrete extract learning from the timeouts:** truthy `wdt:` queries scaled (the 592k-edge query
completed repeatedly); *every* statement/qualifier (`p:`/`pq:`) query timed out. Since we're dropping
ordinals, the real extract needs only `wdt:P31`, `wdt:P161`, `wikibase:sitelinks`, the enwiki
sitelink, and labels — all on the fast path. **Partition by release year** (`wdt:P577`) if a single
pull is too big, and **cache raw results to disk** so the transform stage never re-hits Wikidata.

---

## 6. Queries used

`enwiki` example shown; swap the `WHERE` body per the findings above.

```sparql
# Notability histogram (all films)
SELECT ?bucket (COUNT(?film) AS ?n) WHERE {
  ?film wdt:P31 wd:Q11424 ; wikibase:sitelinks ?s .
  BIND(IF(?s>=50,"f 50+",IF(?s>=20,"e 20-49",IF(?s>=10,"d 10-19",
       IF(?s>=5,"c 5-9",IF(?s>=2,"b 2-4","a 1"))))) AS ?bucket)
} GROUP BY ?bucket ORDER BY ?bucket

# Cast completeness (subquery: per-film count, then bucket the counts)
SELECT ?bucket (COUNT(?film) AS ?n) WHERE {
  { SELECT ?film (COUNT(?actor) AS ?cast) WHERE {
      ?film wdt:P31 wd:Q11424 ; wikibase:sitelinks ?s ; wdt:P161 ?actor .
      FILTER(?s >= 5)
    } GROUP BY ?film }
  BIND(IF(?cast>=10,"c 10+",IF(?cast>=3,"b 3-9","a 1-2")) AS ?bucket)
} GROUP BY ?bucket ORDER BY ?bucket

# Raw cast edges at a threshold
SELECT (COUNT(*) AS ?edges) WHERE {
  ?film wdt:P31 wd:Q11424 ; wikibase:sitelinks ?s ; wdt:P161 ?actor .
  FILTER(?s >= 5)
}

# Ordinal (P1545) coverage — SUM(IF(BOUND())) idiom. NOTE: times out above ~836 films;
# run only on a small high-threshold sample (>=50) for a ceiling estimate.
SELECT (COUNT(*) AS ?stmts) (SUM(IF(BOUND(?ord),1,0)) AS ?withOrd) WHERE {
  ?film wdt:P31 wd:Q11424 ; wikibase:sitelinks ?s ; p:P161 ?stmt .
  FILTER(?s >= 50)
  OPTIONAL { ?stmt pq:P1545 ?ord . }
}

# Recognizability spot-check (qualitative)
SELECT ?filmLabel ?s WHERE {
  ?film wdt:P31 wd:Q11424 ; wikibase:sitelinks ?s .
  FILTER(?s = 5)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} LIMIT 30

# enwiki-anchored film count
SELECT (COUNT(DISTINCT ?film) AS ?films) WHERE {
  ?film wdt:P31 wd:Q11424 .
  ?art schema:about ?film ; schema:isPartOf <https://en.wikipedia.org/> .
}
```

---

## 7. Open items / next step

- Exact size of `enwiki ∩ ≥5 ∩ ≥3 cast` not measured (clearly ~50k; not blocking).
- Documentary/TV exclusion (`Q93204`, `Q506240`) not yet quantified.
- **Next:** design the partitioned, resumable, disk-cached **extract stage** (threshold as a
  parameter), per §4–§5.
