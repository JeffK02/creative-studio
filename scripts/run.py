#!/usr/bin/env python3
"""Creative Studio orchestrator.

    python scripts/run.py acme-serum --concepts 15
    python scripts/run.py acme-serum --stage concepts   # resume from a stage

Stages run in order and each writes its output to disk, so a failed run is
resumable rather than a full restart. Read the JSON between stages while you're
still tuning prompts — that's the whole point of writing them out.
"""

import argparse
import csv
import datetime as dt
import json
import math
import shutil
from pathlib import Path

import yaml

import llm
import images as img_mod
import export
import fetch_lp
import metrics as metrics_mod

ROOT = Path(__file__).resolve().parent.parent
CONFIG = llm.CONFIG
ARCHETYPES = yaml.safe_load((ROOT / CONFIG["paths"]["archetypes"]).read_text())

STAGES = ["identify", "teardown", "brief", "concepts", "score",
          "briefs", "images", "export", "copy"]


# ---------------------------------------------------------------- helpers

def products_root() -> Path:
    """Supports an absolute path (e.g. a Google Drive synced folder) so the
    media buyer can drop assets without touching the repo."""
    raw = Path(CONFIG["paths"]["products"])
    return raw if raw.is_absolute() else ROOT / raw


def product_dir(slug: str) -> Path:
    d = products_root() / slug
    if not d.exists():
        raise SystemExit(f"No such product: {d}")
    return d


def read(path: Path, default: str = "") -> str:
    return path.read_text() if path.exists() else default


def images_in(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(f for f in folder.iterdir()
                  if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})


def seed_creatives(p: Path):
    """Round 1: images dropped into winners/ and losers/, with metrics read
    straight from a Meta Ads Manager export."""
    wins, losses = images_in(p / "winners"), images_in(p / "losers")
    all_names = [f.name for f in wins + losses]
    if not all_names:
        raise SystemExit(f"No creative images in {p / 'winners'} or {p / 'losers'}")

    csv_path = p / "metrics.csv"
    if not csv_path.exists():
        raise SystemExit(
            f"metrics.csv missing in {p}\n"
            f"Export the ad-level report from Meta Ads Manager and save it there.")

    data, unmatched, missing = metrics_mod.load(csv_path, all_names)
    for name in unmatched:
        print(f"  ! metrics.csv row '{name}' matches no image file")
    for name in missing:
        print(f"  ! image '{name}' has no row in metrics.csv")
    if not data:
        raise SystemExit(
            "metrics.csv matched none of the images.\n"
            "Name each image file after its Ad name in Ads Manager "
            "(e.g. ad 'w_001' -> w_001.jpg).")

    return (wins, metrics_mod.as_prompt_text([f.name for f in wins], data),
            losses, metrics_mod.as_prompt_text([f.name for f in losses], data))


def find_image(p: Path, creative_id: str) -> Path | None:
    """Locate a creative image anywhere in the product folder — a hand-uploaded
    seed, or something this system generated in an earlier run."""
    for folder in (p / "winners", p / "losers"):
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            cand = folder / f"{creative_id}{ext}"
            if cand.exists():
                return cand
    hits = sorted(p.glob(f"runs/*/base/{creative_id}_pick.*"))
    if hits:
        return hits[-1]
    hits = sorted(p.glob(f"runs/*/base/{creative_id}_1.*"))
    return hits[-1] if hits else None


def scored_creatives(p: Path) -> tuple[list[Path], str, list[Path], str]:
    """Round 2+: pull the best and worst performers straight from log.csv.

    This is what lets the system read its own output back. Everything it has
    ever generated is in the log with results; the teardown looks at the top
    and bottom of that list rather than a folder someone has to keep updating.
    """
    log_path = p / "log.csv"
    if not log_path.exists():
        return [], "", [], ""
    rows = [r for r in csv.DictReader(log_path.open()) if r.get("ROAS")]
    def as_float(r):
        try:
            return float(r["ROAS"])
        except (ValueError, TypeError):
            return None
    rows = [r for r in rows if as_float(r) is not None]
    if len(rows) < 4:
        return [], "", [], ""
    rows.sort(key=as_float, reverse=True)
    n_w = CONFIG["teardown"]["top_winners"]
    n_l = CONFIG["teardown"]["top_losers"]
    winners, losers = rows[:n_w], rows[-n_l:]

    def block(rs, label):
        out = [f"# {label} (from log.csv)"]
        for r in rs:
            img = find_image(p, r["creative_id"])
            out += [
                f"\n## {r['creative_id']}",
                f"- file: {img.name if img else 'IMAGE NOT FOUND'}",
                f"- market: {r.get('market','')}",
                f"- headline: {r.get('headline','')}",
                f"- angle: {r.get('angle','')}",
                f"- archetype: {r.get('archetype','')}",
                f"- hypothesis: {r.get('hypothesis','')}",
                f"- CTR: {r.get('CTR','')}",
                f"- CPM: {r.get('CPM','')}",
                f"- CVR: {r.get('CVR','')}",
                f"- ROAS: {r.get('ROAS','')}",
                f"- confidence: {r.get('confidence','')}",
            ]
        return "\n".join(out)

    w_imgs = [i for i in (find_image(p, r["creative_id"]) for r in winners) if i]
    l_imgs = [i for i in (find_image(p, r["creative_id"]) for r in losers) if i]
    return w_imgs, block(winners, "Winning creatives"), l_imgs, block(losers, "Losing creatives")


def templates_reference() -> str:
    """Render templates.yaml as prompt-injectable text, with hard char limits."""
    lines = []
    for name, spec in ARCHETYPES["templates"].items():
        lines.append(f"### {name}")
        lines.append(spec["description"].strip())
        lines.append(f"render_mode: {spec.get('render_mode', 'template')}")
        for field, rules in spec["fields"].items():
            opt = " (optional)" if rules.get("optional") else ""
            lines.append(f"- `{field}` — MAX {rules['max_chars']} characters{opt}")
        if spec.get("notes"):
            lines.append(f"Note: {spec['notes']}")
        lines.append("")
    return "\n".join(lines)


def mix_counts(n: int) -> dict:
    """Turn mix proportions into integer counts summing to n."""
    mix = CONFIG["concepts"]["mix"]
    counts = {k: int(math.floor(v * n)) for k, v in mix.items()}
    while sum(counts.values()) < n:                      # give remainder to new_angle
        counts["new_angle"] += 1
    return counts


# ---------------------------------------------------------------- stages

def stage_teardown(p: Path, run: Path):
    # Round 2+: everything the system has generated, ranked by actual results.
    win_imgs, win_meta, lose_imgs, lose_meta = scored_creatives(p)
    if win_imgs:
        print(f"  using {len(win_imgs)} winners / {len(lose_imgs)} losers from log.csv")
    else:
        # Round 1: hand-uploaded seed creatives.
        win_imgs, win_meta, lose_imgs, lose_meta = seed_creatives(p)
    if not win_imgs:
        raise SystemExit("No winner images found in winners/")
    if not lose_imgs:
        print("  ! No losers/ — teardown will run, but diagnosis quality drops sharply.")

    prompt = llm.load_prompt(
        "01-teardown",
        winner_metrics=win_meta or "(none supplied)",
        loser_metrics=lose_meta or "(none supplied)",
        templates=templates_reference(),
    )
    data = llm.call_json("teardown", prompt, images=win_imgs + lose_imgs)
    (run / "teardown.json").write_text(json.dumps(data, indent=2))
    print(f"  teardown: {len(data)} creatives analysed")


def stage_identify(p: Path, run: Path):
    """Derive name, problem, price and offer from the pages themselves, so
    nobody has to type them — and so the problem cache key stays consistent
    across products instead of drifting with whoever filled the form."""
    derived = p / "_derived"
    derived.mkdir(exist_ok=True)

    if not (derived / "pages.md").exists():
        print("  fetching pages")
        fetch_lp.run(p.name, products_root=products_root())

    ident_path = derived / "identity.json"
    if ident_path.exists():
        print(f"  cached: {json.loads(ident_path.read_text())['problem_slug']}")
        return

    prompt = llm.load_prompt(
        "01-identify",
        pages=read(derived / "pages.md"),
        notes=read(p / "notes.md", "(none)"),
    )
    ident = llm.call_json_obj("image_prompts", prompt)   # Sonnet — extraction only
    ident_path.write_text(json.dumps(ident, indent=2), encoding="utf-8")
    print(f"  {ident['product_name']} — problem: {ident['problem_slug']} "
          f"({ident.get('language')})")


def stage_brief(p: Path, run: Path):
    derived = p / "_derived"
    ident = json.loads((derived / "identity.json").read_text())
    slug = ident["problem_slug"]
    dossier_path = ROOT / CONFIG["paths"]["problems"] / slug / "dossier.md"

    if not dossier_path.exists():
        print(f"  no dossier for '{slug}' — writing and caching it")
        dp = llm.load_prompt(
            "00-problem-dossier",
            problem=f"{slug}: {ident.get('problem_description','')}",
            pages=read(derived / "pages.md"),
        )
        dossier_path.parent.mkdir(parents=True, exist_ok=True)
        dossier_path.write_text(llm.call("dossier", dp), encoding="utf-8")
    else:
        print(f"  reusing cached dossier: {slug}")

    prompt = llm.load_prompt(
        "02-product-brief",
        identity=json.dumps(ident, indent=2),
        pages=read(derived / "pages.md"),
        notes=read(p / "notes.md", "(none)"),
        problem_dossier=read(dossier_path, "(none)"),
        teardown=read(run / "teardown.json"),
    )
    (derived / "product-brief.md").write_text(
        llm.call("product_brief", prompt), encoding="utf-8")
    print("  product brief written")


def stage_concepts(p: Path, run: Path, n: int):
    bank_path = p / "concept-bank.json"
    prompt = llm.load_prompt(
        "03-concepts",
        overgenerate=CONFIG["concepts"]["overgenerate"],
        mix=json.dumps(mix_counts(n), indent=2),
        spread=json.dumps(CONFIG["concepts"]["spread"], indent=2),
        product_brief=read(p / "_derived/product-brief.md"),
        teardown=read(run / "teardown.json"),
        tested_angles=read(p / "tested-angles.md", "(nothing tested yet)"),
        concept_bank=read(bank_path, "[]"),
        mechanisms=read(p / "_derived/mechanisms.md", "(not generated — fast lane)"),
        beliefs=read(p / "_derived/beliefs.md", "(not generated — fast lane)"),
        desires=read(p / "_derived/desires.md", "(not generated — fast lane)"),
        frameworks=read(ROOT / "knowledge/frameworks.md"),
        static_translation=read(ROOT / "knowledge/static-translation.md"),
        templates=templates_reference(),
    )
    data = llm.call_json("concepts", prompt)
    (run / "concepts.json").write_text(json.dumps(data, indent=2))
    print(f"  concepts: {len(data)} generated")


def stage_score(p: Path, run: Path, n: int):
    prompt = llm.load_prompt(
        "04-score",
        n=n,
        concepts=read(run / "concepts.json"),
        tested_angles=read(p / "tested-angles.md", "(nothing tested yet)"),
        log_summary=summarise_log(p),
        spread=json.dumps(CONFIG["concepts"]["spread"], indent=2),
    )
    result = llm.call_json_obj("score", prompt)
    (run / "selected.json").write_text(json.dumps(result["selected"], indent=2))
    (p / "concept-bank.json").write_text(json.dumps(result.get("banked", []), indent=2))
    print(f"  selected {len(result['selected'])}, banked {len(result.get('banked', []))}")


def stage_briefs(p: Path, run: Path):
    prompt = llm.load_prompt(
        "05-briefs",
        selected=read(run / "selected.json"),
        product_brief=read(p / "_derived/product-brief.md"),
        templates=templates_reference(),
        frameworks=read(ROOT / "knowledge/frameworks.md"),
        static_translation=read(ROOT / "knowledge/static-translation.md"),
    )
    data = llm.call_json("briefs", prompt)
    validate_briefs(data)
    (run / "briefs.json").write_text(json.dumps(data, indent=2))
    print(f"  briefs: {len(data)} written")


def stage_images(p: Path, run: Path):
    briefs = json.loads((run / "briefs.json").read_text())
    refs = sorted((p / "reference").glob("*"))
    if not refs:
        raise SystemExit("No reference images in reference/")
    img_mod.generate(briefs, refs, run / "base")
    img_mod.contact_sheet(run / "base", run / "contact-sheet.html")
    print(f"  images -> {run / 'base'}   review: {run / 'contact-sheet.html'}")


def stage_export(p: Path, run: Path):
    export.to_canva_csv(run / "briefs.json", run / "base", run / "canva.csv")
    export.append_log(p / "log.csv", run / "briefs.json", run.name)
    print(f"  canva.csv written; log.csv updated")


def stage_copy(p: Path, run: Path):
    ident = json.loads((p / "_derived/identity.json").read_text())
    prompt = llm.load_prompt(
        "07-ad-copy",
        product_name=ident["product_name"],
        offer=ident.get("offer_summary", ""),
        product_brief=read(p / "_derived/product-brief.md"),
        selected=read(run / "selected.json"),
        winner_copy=read(p / "copy.md", "(none supplied)"),
        beliefs=read(p / "_derived/beliefs.md", "(fast lane — none)"),
    )
    (run / "ad-copy.md").write_text(llm.call("ad_copy", prompt))
    print("  ad copy written")


# ---------------------------------------------------------------- validation

def validate_briefs(briefs: list[dict]):
    """Hard-fail on character overruns. Canva will not auto-fit; catching it
    here costs one retry, catching it in Canva costs your editor a day."""
    problems = []
    for b in briefs:
        spec = ARCHETYPES["templates"].get(b.get("template"))
        if not spec:
            problems.append(f"{b.get('concept_id')}: unknown template {b.get('template')}")
            continue
        for field, rules in spec["fields"].items():
            val = b.get(field)
            if val is None:
                if not rules.get("optional"):
                    problems.append(f"{b['concept_id']}: missing {field}")
                continue
            if len(val) > rules["max_chars"]:
                problems.append(
                    f"{b['concept_id']}.{field}: {len(val)} chars > {rules['max_chars']}")
        for required in ("hypothesis", "angle", "source", "image_prompt"):
            if not b.get(required):
                problems.append(f"{b.get('concept_id')}: missing {required}")
    if problems:
        print("  ! brief validation issues:")
        for x in problems:
            print("     ", x)
        print("  Fix by re-running the briefs stage, or edit briefs.json by hand.")


def summarise_log(p: Path) -> str:
    """Feed the scorer its own hit rate. This is what makes the system learn."""
    path = p / "log.csv"
    if not path.exists():
        return "(no results logged yet)"
    rows = list(csv.DictReader(path.open()))
    scored = [r for r in rows if r.get("ROAS")]
    if not scored:
        return "(no results logged yet)"
    by_angle: dict[str, list[float]] = {}
    for r in scored:
        try:
            by_angle.setdefault(r.get("archetype", "?"), []).append(float(r["ROAS"]))
        except ValueError:
            continue
    lines = ["Historical ROAS by archetype:"]
    for k, v in sorted(by_angle.items(), key=lambda x: -sum(x[1]) / len(x[1])):
        lines.append(f"- {k}: avg {sum(v)/len(v):.2f} across {len(v)} creatives")
    return "\n".join(lines)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("--concepts", type=int, default=CONFIG["concepts"]["default_n"])
    ap.add_argument("--stage", choices=STAGES, help="resume from this stage")
    ap.add_argument("--stop-after", choices=STAGES,
                    help="stop after this stage — use --stop-after concepts on "
                         "a new product to sanity-check range before paying for images")
    ap.add_argument("--run", help="reuse an existing run folder (YYYY-MM-DD)")
    args = ap.parse_args()

    p = product_dir(args.product)
    run_name = args.run or dt.date.today().isoformat()
    run = p / "runs" / run_name
    run.mkdir(parents=True, exist_ok=True)

    start = STAGES.index(args.stage) if args.stage else 0
    end = STAGES.index(args.stop_after) + 1 if args.stop_after else len(STAGES)
    for stage in STAGES[start:end]:
        print(f"[{stage}]")
        if stage == "identify":
            stage_identify(p, run)
        elif stage == "teardown":
            stage_teardown(p, run)
        elif stage == "brief":
            stage_brief(p, run)
        elif stage == "concepts":
            stage_concepts(p, run, args.concepts)
        elif stage == "score":
            stage_score(p, run, args.concepts)
        elif stage == "briefs":
            stage_briefs(p, run)
        elif stage == "images":
            stage_images(p, run)
        elif stage == "export":
            stage_export(p, run)
        elif stage == "copy":
            stage_copy(p, run)

    if args.stop_after:
        print(f"\nStopped after {args.stop_after}. Output in {run}")
        return

    print(f"\nDone. {run}")
    print(f"  1. Review {run / 'contact-sheet.html'} and pick one variant per brief")
    print(f"  2. Upload {run / 'canva.csv'} to Canva Bulk Create")
    print(f"  3. Ad copy: {run / 'ad-copy.md'}")


if __name__ == "__main__":
    main()
