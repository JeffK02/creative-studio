# Local Setup

Everything here runs on **your own machine**, not in a sandbox. The Higgsfield
auth step opens a browser, so it was always going to be local.

Estimated time: 30–45 minutes, most of it waiting on downloads.

You're on Windows, so commands below are PowerShell unless noted. Keep the
whole system on one machine — this is the "technical person" machine, and for
now that is you.

---

## 1. Node.js — needed for the Higgsfield CLI

Check whether you already have it:

```bash
node --version
```

If you get a version number of 18 or higher, skip to step 2.

**macOS:** install Homebrew first if you don't have it, then Node.

Download the LTS installer from nodejs.org, run it, accept the defaults. Then
open a **new** PowerShell window — the old one won't see it on PATH.

Verify:

```bash
node --version
npm --version
```

---

## 2. Higgsfield CLI

```bash
npm i -g @higgsfield/cli
```

Already done on your machine. Authenticate — this opens a browser:

```bash
higgsfield auth login
```

Sign in with the account holding your subscription. Then install the companion
skills:

```bash
npx skills add higgsfield-ai/skills
```

### Probe it before trusting it

`scripts/images.py` is now written against the real CLI: upload → create job →
wait → download. What isn't documented is the **shape of the JSON** each command
returns, so the adapter finds fields by searching for key names rather than
following a fixed path. That's forgiving, but it should be verified before a
full run depends on it.

After setting up the repo (step 4), run:

```powershell
python scripts\probe_higgsfield.py products\acme-serum\reference\front.jpg
```

It does one real generation and prints every response. Costs one image of
credits. If it prints resolved values for `upload_id`, `job_id`, and the media
URL, and downloads `probe-output.png`, the adapter works — set
`images.provider: higgsfield` in `config.yaml`.

If any of the three comes back `None`, paste me the dumped JSON and I'll correct
the field lookup exactly.

Then open `probe-output.png` and check the thing that actually matters: **did
the packaging survive?** Label legible, proportions right, no warping. If it
didn't, no amount of prompt work downstream will fix it, and we should try
`product-photoshoot` instead — see below.

### Two commands worth exploring

Your `--help` output surfaced two I didn't know about:

- **`higgsfield product-photoshoot`** — brand-quality image generation with
  mode-specific prompt enhancement. Built for exactly this use case and may
  beat raw `generate create` on product fidelity. Run
  `higgsfield product-photoshoot --help` and paste it; if it takes a reference
  image and a prompt, it's a drop-in swap in `images.py` worth testing
  head-to-head.
- **`higgsfield soul-id`** — trains a reusable identity reference. Normally for
  faces. If you ever want one consistent UGC persona recurring across a
  product's whole creative set, that's the mechanism. Park it for now.

Also useful:

```powershell
higgsfield model list --image      # what your plan actually exposes
higgsfield generate cost nano_banana_2 --prompt "test"   # credits per image
```

A 15-brief run at 3 variants is 45 generations. Worth knowing the cost per run
before you start doing it weekly.

---

## 3. Python

```powershell
python --version
```

Needs 3.10 or higher. Install from python.org and **tick "Add Python to PATH"**
on the first screen — this is the step people skip and then spend an hour
debugging.

---

## 4. The repo

Unzip it somewhere permanent — `C:\Users\you\creative-studio` is fine.

```powershell
cd C:\Users\you\creative-studio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Set the API key permanently, then open a **new** PowerShell window so it takes:

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY","sk-ant-…","User")
```

Get the key from console.anthropic.com. This is a separate bill from your Claude
subscription.

---

## 5. Version control

```bash
git init
git add .
git commit -m "initial scaffold"
```

Create a private repo on GitHub, then follow the push instructions it gives you.

Nobody else on your team needs git access. They work in Drive and the results
sheet.

---

## 6. Point products at Google Drive

Install Google Drive for Desktop. Create a folder in your shared drive:

```
Creative Studio/products/
```

Then in `config.yaml`:

```yaml
paths:
  products: /Users/you/Library/CloudStorage/GoogleDrive-…/My Drive/Creative Studio/products
```

Your path will look like `G:\My Drive\Creative Studio\products`. In YAML,
backslashes are fine inside single quotes:

```yaml
paths:
  products: 'G:\My Drive\Creative Studio\products'
```

Now the media buyer drops files into a Drive folder and you run the pipeline
against them. No git, no terminal, no training.

Add `products/` to `.gitignore` so client assets don't end up in the repo.

---

## 7. First run

Seed one product:

```
products/acme-serum/
  meta.json                  ← name, price, offer, LP + advertorial URLs
  product-facts.md           ← ingredients, claims, guarantee
  reference/                 ← 3–5 clean product images
  winners/  w_001.jpg …      ← round-1 seed creatives
  winners/metrics.md         ← CTR, CPM, CVR, ROAS, confidence, market
  winners/copy.md            ← the ad copy that ran, verbatim
  losers/   l_001.jpg …      ← 2–3, same fields
```

Then stop early and look:

```bash
python scripts/run.py acme-serum --stop-after concepts
```

Open `products/acme-serum/runs/{today}/concepts.json`. Thirty seconds tells you
whether the batch has real range or has collapsed into fifteen versions of your
winner. Fixing the prompt at that point costs one API call; finding out after
generation costs 45 images.

When it looks right:

```bash
python scripts/run.py acme-serum --stage briefs --run {today}
```

---

## 8. The loop

This is the part that makes it improve rather than repeat.

```bash
python scripts/log.py acme-serum --results ~/Downloads/results.csv
```

`results.csv` needs `creative_id, CTR, CPM, CVR, ROAS, confidence, market`.
Export it from the media buyer's sheet.

This merges results into `log.csv` and rebuilds `tested-angles.md`, which the
next run reads as a negative constraint — the list of angles it must not
propose again.

**From round two onward you never touch `winners/` again.** The teardown pulls
the top 5 and bottom 3 from `log.csv` automatically, images resolved from
previous runs. The system reads its own output back and gets sharper each cycle.

---

## Should you start setting up now?

Steps 1–6 yes — all independent of anything still open.

Then run the probe. It answers the two questions everything else rests on: does
the CLI integration work, and does the packaging survive generation.

A full run also needs `knowledge/frameworks.md` and
`knowledge/static-translation.md`, which aren't written yet. The concepts and
briefs stages both read them, and without them the output will be competent but
generic — the exact failure mode this system exists to avoid. I'll write those
while you set up.
