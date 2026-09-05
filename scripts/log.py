#!/usr/bin/env python3
"""Ingest results and update the product's tested-angles memory.

    python scripts/log.py acme-serum --results ~/Downloads/results.csv

`results.csv` needs only: creative_id, CTR, CPM, CVR, ROAS, confidence,
market. Anything else is ignored. Matching is on creative_id.

Ratios only — spend and impressions scale with budget and are not comparable
across campaigns. `confidence` (low/medium/high) is the media buyer's call on
whether a result spent enough to be trusted.

Then it regenerates tested-angles.md, which stage 3 injects as a NEGATIVE
constraint. This file is the mechanism that stops the system reproducing
angles that already failed — it is the difference between a system that
learns and a content mill.
"""

import argparse
import csv
from pathlib import Path

import llm

ROOT = Path(__file__).resolve().parent.parent
WIN_ROAS = 2.0


def merge(log_path: Path, results_path: Path):
    rows = {r["creative_id"]: r for r in csv.DictReader(log_path.open())}
    updated = 0
    for r in csv.DictReader(results_path.open()):
        cid = r.get("creative_id")
        if cid not in rows:
            print(f"  ! unknown creative_id, skipped: {cid}")
            continue
        for k in ("CTR", "CPM", "CVR", "ROAS", "confidence", "market"):
            if r.get(k):
                rows[cid][k] = r[k]
        try:
            rows[cid]["verdict"] = "winner" if float(r.get("ROAS", 0)) >= WIN_ROAS else "loser"
        except ValueError:
            pass
        updated += 1

    with log_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = list(next(iter(rows.values())).keys())
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows.values())
    print(f"  {updated} rows updated")
    return list(rows.values())


def rebuild_tested_angles(product_dir: Path, rows: list[dict]):
    scored = [r for r in rows if r.get("verdict")]
    if not scored:
        print("  nothing scored yet — tested-angles.md unchanged")
        return

    def block(rs):
        return "\n".join(
            f"- [{r['archetype']}] {r['angle']} | desire: {r.get('desire','?')} | "
            f"ROAS {r.get('ROAS','?')} ({r.get('confidence','?')} confidence) | "
            f"hypothesis: {r.get('hypothesis','')}"
            for r in rs) or "(none)"

    winners = [r for r in scored if r["verdict"] == "winner"]
    losers = [r for r in scored if r["verdict"] == "loser"]

    prompt = f"""You maintain a running memory of what has been tested for one product.

WINNERS:
{block(winners)}

LOSERS:
{block(losers)}

Write `tested-angles.md`. Sections, markdown only, no preamble:

## Proven angles
Angles that won, with what specifically worked. These may be iterated on.

## Dead angles
Angles that failed. State the angle plainly and, where the evidence supports it,
what appears to have killed it. Be precise about scope: "sleep-quality angle
failed" is useful; "emotional angles failed" over-generalises from thin data.

## Exhausted executions
Executions used enough times that repeating them risks fatigue, even where the
underlying angle is proven.

## Untested territory
Desires, beliefs, buyers, and archetypes that appear in neither list.

Weight low-confidence results down — a strong ROAS that barely spent is not
evidence, and treating it as such narrows the next batch around noise.
Where evidence rests on one or two creatives, say so. Do not present a thin
result as settled — that is how a system talks itself out of a good angle.
"""
    out = llm.call("dossier", prompt)
    (product_dir / "tested-angles.md").write_text(out)
    print(f"  tested-angles.md rebuilt ({len(winners)} winners, {len(losers)} losers)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("product")
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    pdir = ROOT / "products" / args.product
    log_path = pdir / "log.csv"
    if not log_path.exists():
        raise SystemExit(f"No log at {log_path}")
    rows = merge(log_path, Path(args.results))
    rebuild_tested_angles(pdir, rows)


if __name__ == "__main__":
    main()
