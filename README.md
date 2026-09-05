# Creative Studio

Static image ad generation for dropshipping. One product in, N briefs out —
iterations of proven winners plus genuinely untested angles.

---

## Part 1 — What you need to provide

Nothing below requires a terminal. Do these before the first run.

### 1.1 Per product entering the system

Copy `products/_template/` and rename it after the product. Four things to fill:

| What | Effort |
|---|---|
| `links.txt` | paste the landing page, advertorial and **checkout page** URLs |
| `reference/` | drop in 3–5 clean product photos |
| `winners/` + `losers/` | drop in the creatives, named after their Ad name |
| `metrics.csv` | Ads Manager → Reports → Export CSV, dropped in as-is |

Optional: `copy.md` (the ad copy that ran) and `notes.md` (free text).

Everything else — product name, price of each variant, offer, what problem it
solves — is read off the pages by the `identify` stage and cached in `_derived/`.
Nothing is typed twice, and nothing depends on someone summarising a page
correctly.

**Name image files after their Ad name in Ads Manager.** That is how metric rows
get matched to images. Ad `w_001` → `w_001.jpg`. It's a rename they're doing
anyway, and it makes matching exact.

**The export goes in raw.** Column names are matched by keyword, so the default
Meta export works without reformatting — no retyping numbers, no hand-built
spreadsheet. `confidence` is derived automatically from Amount spent, so nobody
has to make that judgement.

**On losers.** The field most likely to get skipped and the one that pays best.
A system that only sees winners cannot recognise a bad idea, and will
confidently propose angles that already failed.

**Why the metrics matter.** They drive the diagnosis that decides what the next
batch varies:

- **CPM against CTR** — high CPM with low CTR means Meta is reading the creative
  as low-quality or too ad-like. A different failure from "boring image", and a
  different fix.
- **CVR against CTR** — high CTR with low CVR means the ad is working and the
  claim underneath it is wrong. Instinct says make a prettier ad; the numbers say
  change what it promises.

### 1.4 Where things live

| What | Where | Who touches it |
|---|---|---|
| Code, prompts, knowledge, templates | private GitHub repo | you |
| `products/{slug}/` assets and metrics | Google Drive (synced folder) | media buyer, editor |
| Results log | Google Sheet, exported as CSV | media buyer |

Point `paths.products` in `config.yaml` at your Drive-synced folder. Nobody on
the team needs git — they see a Drive folder and a sheet.

---

### 1.5 Rounds after the first

From round 2 onward the teardown pulls the top 5 and bottom 3 creatives
**straight from `log.csv`**, resolving images from previous runs. Nobody
updates `winners/` again.

The cycle:

```
run.py  →  15 creatives  →  test them  →  log.py --results  →  run.py
```

Each pass, the system sees everything it has generated ranked by real
performance, and `tested-angles.md` rebuilds as a negative constraint. This
loop is the difference between a system that learns and a content mill.

---

## Part 2 — Setup

Full machine setup — Node, Higgsfield CLI, Python, Drive — is in `SETUP.md`.
The short version:

```bash
git init creative-studio && cd creative-studio      # or unzip this scaffold
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-…                   # put this in your shell rc
```

Then, in order:

1. **Write the knowledge docs.** Nothing works well without them. The concepts
   stage reads both.
2. **Set `images.provider: manual`** in `config.yaml`. Get the pipeline working
   end to end before automating image generation.
3. **No templates needed.** Every archetype is `full_generate` — the image
   model renders the finished ad, text included, and your editor fixes what
   comes out broken.

   After the first batch, count how many needed manual text fixing. If a
   specific archetype fails most of the time — `comparison` and `three_callout`
   are the likeliest — switch that one to `render_mode: template` in
   `templates/archetypes.yaml` rather than abandoning it.

---

## Part 3 — Running it

```bash
python scripts/run.py acme-serum --concepts 15
```

Stages run in order, each writing its output to
`products/acme-serum/runs/{today}/`. Resume from any stage:

```bash
python scripts/run.py acme-serum --stage concepts --run 2026-08-28
```

| Stage | Output | Model |
|---|---|---|
| teardown | `teardown.json` | Opus 5 |
| brief | `product-brief.md` | Opus 5 |
| concepts | `concepts.json` (25) | Opus 5 |
| score | `selected.json` (15), `concept-bank.json` | Sonnet 5 |
| briefs | `briefs.json` | Opus 5 |
| images | `base/`, `contact-sheet.html` | Higgsfield |
| export | `canva.csv`, appends `log.csv` | — |
| copy | `ad-copy.md` | Opus 5 |

On a product's first run, stop early and look:

```bash
python scripts/run.py acme-serum --stop-after concepts
```

`concepts.json` tells you in thirty seconds whether the batch has real range or
has collapsed into fifteen versions of your winner. Fixing the prompt at that
point costs one call; finding out after generation costs 45 images.

**While you are still tuning prompts, read the JSON between stages.** That is
why every stage writes to disk. `concepts.json` in particular tells you within
thirty seconds whether the batch has real range or has collapsed into fifteen
versions of the winner.

### After the run

1. Open `contact-sheet.html`, pick one variant per concept, copy it to
   `base/{concept_id}_pick.png`. The picked filename is what round 2's teardown
   looks for, so don't skip the rename.
2. `canva.csv` is only written if you have switched an archetype back to
   `template` mode.
3. Editor fixes any garbled text on the generated images and exports.
4. Ad copy is in `ad-copy.md`.

### After the test

```bash
python scripts/log.py acme-serum --results ~/Downloads/results.csv
```

`results.csv` needs only `creative_id` plus the metric columns. This merges
results into `log.csv` and rebuilds `tested-angles.md`, which the next run reads
as a negative constraint.

**This step is the whole system.** Skip it and you have a fast content mill that
never learns. Run it every cycle and the concept stage gets progressively better
at knowing what works for your products specifically.

---

## Part 4 — Killing a product

```bash
mkdir -p archive && mv products/dead-product archive/
```

Never delete. The dossier, briefs, and results stay useful: if the skeptic angle
with an ingredient callout wins across three dead skincare products, that is a
strong prior for the next skincare product you test. With daily testing in one
niche, this archive becomes more valuable than any single product in it.

---

## Part 5 — Build order

**Phase 1 — prove the briefs (week 1–2, no code).**
Write the knowledge docs. Run the prompts by hand in a Claude Project on one
product. Canva manually. Ship 15 creatives.

The only question that matters: *do these briefs produce winners?* If they do
not, automating them produces losers faster and burns image credits doing it.
Nothing else gets built until this answers yes.

**Phase 2 — automate (week 3–5).**
This scaffold. Templates built. Higgsfield wired. `manual` provider first, then
the CLI once you have checked their current interface.

**Phase 3 — close the loop (week 6–8).**
`log.py` running every cycle. `tested-angles.md` auto-updating. Concept bank
re-scoring. The scorer reading its own hit rate.

**Phase 4 — remove the terminal (later, optional).**
HTML templates with auto-fit replace Canva Bulk Create — this permanently kills
text overflow and makes multi-language rendering a loop instead of a job. A
watched Drive folder replaces the command line. Meta API pulls results
automatically.

Do not build Phase 4 before Phase 3 works.

---

## Known gaps

- **`fetch_lp.py` uses a dependency-free HTML stripper.** Fine for most landing
  pages; JavaScript-rendered pages return almost nothing and it will tell you
  so. Paste those in by hand.

- **`scripts/images.py` `_higgsfield()` is a template, not working code.** The
  CLI argument names are guesses. Install the CLI locally
  (`npm i -g @higgsfield/cli`, `higgsfield auth login`,
  `npx skills add higgsfield-ai/skills`), run `higgsfield generate --help`, and
  correct the command construction. Use `manual` mode until then.
- **The `max_chars` values in `templates/archetypes.yaml`** are sized for
  English on a 1080×1080 frame. Tighten any that come back illegible from the
  image model.
- **The deep-lane prompts** (`prompts/deep/`) are empty. Your existing
  Desire-To-Scale chain goes there, converted to `{{variable}}` placeholders
  with enforced output schemas.
- **None of this code has been run.** It is syntax-checked only — there was no
  network access to test API calls against. Expect small fixes on first run.
#   c r e a t i v e s - s t u d i o  
 