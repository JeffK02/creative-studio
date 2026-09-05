"""Base image generation (Layer A) + contact sheet for review.

Higgsfield CLI flow, from `higgsfield --help`:

    higgsfield upload <file> --json                 -> upload_id
    higgsfield generate create <model> \
        --prompt "..." --image <upload_id> --json   -> job_id
    higgsfield generate wait <job_id> --json        -> result with media URL

Reference images are uploaded once per product and the upload_id cached, so a
15-brief run does one upload rather than 45.

Set `images.provider: manual` in config.yaml to skip generation and get a
prompts.md to paste into the UI instead.
"""

import json
import re
import subprocess
import urllib.request
from pathlib import Path

import yaml

import llm

CONFIG = llm.CONFIG
ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = yaml.safe_load((ROOT / CONFIG["paths"]["archetypes"]).read_text())["templates"]

HF = CONFIG["images"].get("cli", "higgsfield")


# ---------------------------------------------------------------- archetypes

def render_mode(template_name: str) -> str:
    return TEMPLATES.get(template_name, {}).get("render_mode", "full_generate")


def full_prompt(brief: dict) -> str:
    """For full_generate archetypes, append the on-image text so the model
    renders the finished ad."""
    spec = TEMPLATES.get(brief.get("template"), {})
    parts = [brief["image_prompt"]]
    texts = [brief[f] for f in spec.get("fields", {}) if brief.get(f)]
    if texts:
        joined = " / ".join(f'"{x}"' for x in texts)
        parts.append(
            f"Render this text into the image, clean and legible, bold "
            f"sans-serif, high contrast against the background: {joined}. "
            f"Spelling must be exact. No other text anywhere in the image.")
    return " ".join(parts)


def prompt_for(brief: dict) -> str:
    return full_prompt(brief) if render_mode(brief.get("template")) == "full_generate" \
        else brief["image_prompt"]


# ---------------------------------------------------------------- CLI plumbing

def hf(*args, timeout=600):
    """Run the CLI with --json and parse. Returns raw text if not JSON."""
    cmd = [HF, *args, "--json"]
    try:
        r = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise SystemExit(
            f"'{HF}' not found on PATH. Install it (npm i -g @higgsfield/cli) "
            f"or set images.provider: manual in config.yaml")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"{' '.join(cmd[:4])} failed:\n{e.stderr.strip()[:400]}")
    out = r.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return out


def _find(obj, *keys):
    """Depth-first search for the first matching key. The CLI's exact JSON
    shape isn't documented, so fields are located by name rather than by path —
    this survives a nesting change that a hardcoded path would not."""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj and obj[k] is not None:
                return obj[k]
        for v in obj.values():
            found = _find(v, *keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find(v, *keys)
            if found is not None:
                return found
    return None


def _find_media_url(obj):
    url = _find(obj, "url", "image_url", "output_url", "result_url", "media_url")
    if isinstance(url, str) and url.startswith("http"):
        return url
    blob = obj if isinstance(obj, str) else json.dumps(obj)
    m = re.search(r"https?://[^\s\"']+\.(?:png|jpe?g|webp)", blob)
    return m.group(0) if m else None


def upload(path: Path) -> str:
    res = hf("upload", str(path))
    uid = _find(res, "upload_id", "id", "uploadId")
    if not uid:
        raise RuntimeError(f"Could not read upload_id from:\n{str(res)[:400]}")
    return str(uid)


def cached_upload(ref: Path) -> str:
    """Upload each reference image once per product, then reuse the id."""
    cache_file = ref.parent / ".upload_ids.json"
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    key = f"{ref.name}:{ref.stat().st_size}"
    if key not in cache:
        print(f"    uploading reference {ref.name}")
        cache[key] = upload(ref)
        cache_file.write_text(json.dumps(cache, indent=2))
    return cache[key]


def download(url: str, dest: Path):
    with urllib.request.urlopen(url, timeout=180) as r:
        dest.write_bytes(r.read())


# ---------------------------------------------------------------- generation

def generate(briefs, refs, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    provider = CONFIG["images"]["provider"]
    if provider == "manual":
        _manual(briefs, refs, out)
    elif provider == "higgsfield":
        _higgsfield(briefs, refs, out)
    else:
        raise SystemExit(f"Unknown image provider: {provider}")


def _manual(briefs, refs, out):
    lines = ["# Image prompts — paste into Higgsfield",
             "",
             f"Reference: {', '.join(r.name for r in refs)}",
             f"Aspect: {CONFIG['images']['aspect_ratio']}   "
             f"Variants each: {CONFIG['images']['variants_per_brief']}",
             "",
             "Save outputs here as `{concept_id}_1.png`, `{concept_id}_2.png`, …",
             ""]
    for b in briefs:
        lines += [f"## {b['concept_id']} — {b.get('template')} "
                  f"[{render_mode(b.get('template'))}]",
                  "", prompt_for(b), ""]
    (out / "prompts.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  manual mode — prompts at {out / 'prompts.md'}")


def _higgsfield(briefs, refs, out):
    model = CONFIG["images"]["model"]
    aspect = CONFIG["images"]["aspect_ratio"]
    n = CONFIG["images"]["variants_per_brief"]
    extra = CONFIG["images"].get("extra_args", [])

    upload_id = cached_upload(refs[0])
    failures = []

    for b in briefs:
        prompt = prompt_for(b)
        for i in range(1, n + 1):
            dest = out / f"{b['concept_id']}_{i}.png"
            if dest.exists():
                continue
            try:
                created = hf("generate", "create", model,
                             "--prompt", prompt,
                             "--image", upload_id,
                             "--aspect-ratio", aspect,
                             *extra)
                job_id = _find(created, "job_id", "id", "jobId")
                if not job_id:
                    raise RuntimeError(f"no job id in response: {str(created)[:300]}")

                done = hf("generate", "wait", str(job_id), timeout=900)
                url = _find_media_url(done)
                if not url:
                    raise RuntimeError(f"no media url in result: {str(done)[:300]}")

                download(url, dest)
                print(f"    {dest.name}")
            except Exception as e:
                failures.append(f"{b['concept_id']}_{i}: {e}")
                print(f"    ! {dest.name} failed: {str(e)[:160]}")

    if failures:
        (out / "failures.log").write_text("\n".join(failures), encoding="utf-8")
        print(f"  {len(failures)} generations failed — see failures.log")


# ---------------------------------------------------------------- review

def contact_sheet(base: Path, out_html: Path):
    """Grid of every variant, grouped by concept. Open it, pick one per row,
    then copy your pick to {concept_id}_pick.png — round 2's teardown looks
    for that filename."""
    imgs = sorted(p for p in base.glob("*")
                  if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    groups = {}
    for p in imgs:
        if p.stem.endswith("_pick"):
            continue
        groups.setdefault(p.stem.rsplit("_", 1)[0], []).append(p)

    rows = []
    for cid, files in groups.items():
        cells = "".join(
            f'<figure><img src="base/{f.name}">'
            f'<figcaption>{f.name}</figcaption></figure>' for f in files)
        rows.append(f'<section><h2>{cid}</h2><div class="row">{cells}</div></section>')

    out_html.write_text(f"""<!doctype html><meta charset="utf-8">
<title>Contact sheet</title>
<style>
 body{{font:14px system-ui;margin:24px;background:#fafafa}}
 h2{{margin:24px 0 8px;font-size:15px}}
 .row{{display:flex;gap:12px;flex-wrap:wrap}}
 figure{{margin:0;width:240px}}
 img{{width:100%;border-radius:6px;border:1px solid #ddd}}
 figcaption{{font-size:11px;color:#666;margin-top:4px}}
</style>
<h1>Pick one per concept</h1>
<p>Copy your pick to <code>{{concept_id}}_pick.png</code> in the base folder.</p>
{''.join(rows)}
""", encoding="utf-8")
