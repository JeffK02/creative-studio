"""Read creative metrics from a raw Meta Ads Manager export.

The export's column names vary with how it was configured, so columns are
matched by keyword rather than by exact name. Rows are matched to image files
by ad name: name the image file after the ad name in Ads Manager and matching
is exact.

`confidence` is derived from Amount spent, so nobody has to make that judgement
by hand.
"""

import csv
import re
from pathlib import Path

# Each metric: the keywords that must ALL appear in the column header
# (lowercased), plus keywords that disqualify it. Ordered — first match wins.
COLUMN_RULES = {
    "ad_name":  [(["ad", "name"], ["set", "adset", "campaign"])],
    "CTR":      [(["ctr", "link"], []), (["ctr"], []), (["click-through"], [])],
    "CPM":      [(["cpm"], []), (["cost per 1,000"], []), (["cost per 1000"], [])],
    "CVR":      [(["conversion rate"], []), (["cvr"], []),
                 (["purchase", "rate"], ["cost"])],
    "ROAS":     [(["roas"], []), (["return on ad spend"], [])],
    "spend":    [(["amount spent"], []), (["spend"], ["per"]), (["cost"], ["per"])],
    "market":   [(["country"], []), (["region"], []), (["market"], [])],
}

# Spend thresholds for deriving confidence, in account currency.
CONFIDENCE_BANDS = [(500, "high"), (150, "medium"), (0, "low")]


def _match_column(headers, rules):
    lowered = {h: h.lower() for h in headers if h}
    for musts, nots in rules:
        for original, low in lowered.items():
            if all(m in low for m in musts) and not any(n in low for n in nots):
                return original
    return None


def map_columns(headers) -> dict:
    return {metric: col for metric, rules in COLUMN_RULES.items()
            if (col := _match_column(headers, rules))}


def _num(value):
    """Pull a number out of '1.94%', '€12.40', '2,7' etc."""
    if value is None:
        return None
    s = str(value).strip().replace("%", "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if not s:
        return None
    # European decimal comma: 2,7 -> 2.7 ; but 1,234.56 -> 1234.56
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif s.count(",") == 1 and len(s.split(",")[1]) <= 2:
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def confidence_from_spend(spend):
    if spend is None:
        return ""
    for threshold, label in CONFIDENCE_BANDS:
        if spend >= threshold:
            return label
    return "low"


def _norm(name: str) -> str:
    """Loose key for matching an ad name to a filename."""
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def load(csv_path: Path, image_names) -> tuple[dict, list, list]:
    """Returns (metrics_by_filename, unmatched_rows, images_without_rows)."""
    if not csv_path.exists():
        return {}, [], list(image_names)

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}, [], list(image_names)

    cols = map_columns(rows[0].keys())
    if "ad_name" not in cols:
        # Fall back to a plain 'filename' column if someone hand-wrote the file.
        for candidate in ("filename", "file", "creative", "image"):
            hit = next((h for h in rows[0] if h and h.lower() == candidate), None)
            if hit:
                cols["ad_name"] = hit
                break

    by_norm = {_norm(Path(n).stem): n for n in image_names}
    out, unmatched = {}, []

    for row in rows:
        raw_name = row.get(cols.get("ad_name", ""), "")
        if not raw_name:
            continue
        key = _norm(Path(str(raw_name)).stem)
        filename = by_norm.get(key)
        if not filename:
            # Try containment both ways — ad names often carry extra suffixes.
            filename = next((v for k, v in by_norm.items()
                             if k and (k in key or key in k)), None)
        if not filename:
            unmatched.append(str(raw_name))
            continue

        spend = _num(row.get(cols.get("spend", "")))

        def norm(metric, suffix=""):
            """Normalise to a dot decimal. European exports use '2,7', and
            downstream code sorts creatives with float() — a comma there is a
            crash, not a formatting nit."""
            v = _num(row.get(cols.get(metric, "")))
            return f"{v:g}{suffix}" if v is not None else ""

        out[filename] = {
            "CTR": norm("CTR", "%"),
            "CPM": norm("CPM"),
            "CVR": norm("CVR", "%"),
            "ROAS": norm("ROAS"),
            "market": (row.get(cols.get("market", ""), "") or "").strip(),
            "confidence": confidence_from_spend(spend),
            "_spend": spend,
        }

    missing = [n for n in image_names if n not in out]
    return out, unmatched, missing


def as_prompt_text(image_names, metrics: dict) -> str:
    lines = []
    for name in image_names:
        m = metrics.get(name)
        if not m:
            lines.append(f"- {name} — no metrics")
            continue
        parts = [f"{k}: {v}" for k, v in
                 (("CTR", m["CTR"]), ("CPM", m["CPM"]), ("CVR", m["CVR"]),
                  ("ROAS", m["ROAS"]), ("market", m["market"]),
                  ("confidence", m["confidence"])) if v]
        lines.append(f"- {name} — " + ", ".join(parts))
    return "\n".join(lines)
