"""briefs.json -> canva.csv, and briefs -> log.csv rows."""

import csv
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = yaml.safe_load(
    (ROOT / "templates/archetypes.yaml").read_text())["templates"]

LOG_COLUMNS = [
    "creative_id", "product", "run_date", "template", "archetype", "angle",
    "desire", "life_force", "awareness_stage", "emotional_driver", "source",
    "parent_creative_id", "hypothesis", "headline", "market",
    # filled in later by the media buyer:
    "CTR", "CPM", "CVR", "ROAS", "confidence", "verdict",
]


def to_canva_csv(briefs_path: Path, base_dir: Path, out_csv: Path):
    """One row per creative. Column names must match the Canva template's
    named text fields exactly — Bulk Create matches on the header row."""
    all_briefs = json.loads(briefs_path.read_text())
    # full_generate archetypes come out of the image model finished — they
    # never enter Canva, so keep them out of the CSV.
    briefs = [b for b in all_briefs
              if TEMPLATES.get(b.get("template"), {}).get("render_mode",
                                                          "template") != "full_generate"]
    if not briefs:
        print("  all creatives are full-generate — no canva.csv needed")
        return
    skipped = len(all_briefs) - len(briefs)
    if skipped:
        print(f"  {skipped} full-generate creatives excluded from canva.csv")

    # Union of every field used across the batch, stable order.
    text_fields: list[str] = []
    for b in briefs:
        for k in b:
            if k in {"concept_id", "template", "image_prompt", "hypothesis",
                     "angle", "desire", "life_force", "awareness_stage",
                     "emotional_driver", "source", "parent_creative_id",
                     "archetype", "char_counts"}:
                continue
            if k not in text_fields:
                text_fields.append(k)

    header = ["creative_id", "template", "image"] + text_fields
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for b in briefs:
            cid = b["concept_id"]
            pick = base_dir / f"{cid}_pick.png"
            fallback = base_dir / f"{cid}_1.png"
            image = pick if pick.exists() else fallback
            row = [cid, b.get("template", ""), str(image)]
            row += [b.get(k, "") for k in text_fields]
            w.writerow(row)


def append_log(log_path: Path, briefs_path: Path, run_date: str):
    briefs = json.loads(briefs_path.read_text())
    product = log_path.parent.name
    new = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLUMNS, extrasaction="ignore")
        if new:
            w.writeheader()
        for b in briefs:
            w.writerow({
                "creative_id": b["concept_id"],
                "product": product,
                "run_date": run_date,
                "template": b.get("template", ""),
                "archetype": b.get("archetype", b.get("template", "")),
                "angle": b.get("angle", ""),
                "desire": b.get("desire", ""),
                "life_force": b.get("life_force", ""),
                "awareness_stage": b.get("awareness_stage", ""),
                "emotional_driver": b.get("emotional_driver", ""),
                "source": b.get("source", ""),
                "parent_creative_id": b.get("parent_creative_id", ""),
                "hypothesis": b.get("hypothesis", ""),
                "headline": b.get("headline", b.get("myth", b.get("quote", ""))),
            })
