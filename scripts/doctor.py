#!/usr/bin/env python3
"""Check the setup end to end.

    python scripts/doctor.py                 # environment + config
    python scripts/doctor.py acme-serum      # also check one product's files

Read-only and free — no API calls, no credits. Run it whenever something
behaves oddly.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OK, WARN, FAIL = "  [ok]  ", "  [warn]", "  [FAIL]"
_fails, _warns = [], []


def ok(msg):
    print(f"{OK} {msg}")


def warn(msg):
    print(f"{WARN} {msg}")
    _warns.append(msg)


def fail(msg, fix=""):
    print(f"{FAIL} {msg}")
    if fix:
        print(f"         fix: {fix}")
    _fails.append(msg)


def section(name):
    print(f"\n--- {name} " + "-" * max(0, 56 - len(name)))


# ------------------------------------------------------------------ checks

def check_python():
    section("Python")
    v = sys.version_info
    if v >= (3, 10):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python {v.major}.{v.minor} is too old", "install 3.10 or newer")

    exe = Path(sys.executable)
    if ".venv" in exe.parts:
        ok(f"virtualenv active ({exe})")
    else:
        fail("virtualenv NOT active — packages will be missing or wrong",
             r".venv\Scripts\activate")

    for mod, pkg in [("anthropic", "anthropic"), ("yaml", "PyYAML")]:
        try:
            __import__(mod)
            ok(f"{pkg} installed")
        except ImportError:
            fail(f"{pkg} missing", "pip install -r requirements.txt")


def check_key():
    section("API key")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        fail("ANTHROPIC_API_KEY not set in this shell",
             'set it, then open a NEW terminal window')
    elif not key.startswith("sk-ant-"):
        warn("ANTHROPIC_API_KEY is set but doesn't look like an Anthropic key")
    else:
        ok(f"ANTHROPIC_API_KEY set ({key[:11]}…{key[-4:]})")


def check_config():
    section("Config")
    import yaml
    cfg_path = ROOT / "config.yaml"
    if not cfg_path.exists():
        fail("config.yaml missing")
        return None
    try:
        cfg = yaml.safe_load(cfg_path.read_text())
        ok("config.yaml parses")
    except Exception as e:
        fail(f"config.yaml is invalid YAML: {e}",
             "check the products path is in SINGLE quotes")
        return None

    arch = ROOT / cfg["paths"]["archetypes"]
    if arch.exists():
        names = list(yaml.safe_load(arch.read_text())["templates"])
        ok(f"archetypes.yaml: {len(names)} archetypes ({', '.join(names[:3])}…)")
    else:
        fail(f"archetypes file missing at {arch}")

    raw = Path(cfg["paths"]["products"])
    proot = raw if raw.is_absolute() else ROOT / raw
    if not proot.exists():
        fail(f"products path does not exist: {proot}",
             "create the folder, or fix paths.products in config.yaml")
    else:
        ok(f"products path: {proot}")
        if raw.is_absolute():
            ok("using an external (Drive) products folder")
            probe = proot / ".write-test"
            try:
                probe.write_text("x")
                probe.unlink()
                ok("products folder is writable")
            except Exception as e:
                fail(f"products folder is NOT writable: {e}")
        else:
            warn("products path is inside the repo — fine for testing, but the "
                 "team can't reach it. Point it at Drive when you're ready.")
    return cfg


def check_knowledge():
    section("Knowledge base")
    for name, why in [
        ("frameworks.md", "concepts + briefs stages read this"),
        ("static-translation.md", "concepts + briefs stages read this"),
    ]:
        p = ROOT / "knowledge" / name
        size = p.stat().st_size if p.exists() else 0
        if size > 1000:
            ok(f"{name} ({size:,} bytes)")
        elif size:
            warn(f"{name} is very short ({size} bytes) — {why}")
        else:
            warn(f"{name} is EMPTY — {why}; output will be generic until written")


def check_prompts():
    section("Prompts")
    expected = ["00-problem-dossier", "01-teardown", "02-product-brief",
                "03-concepts", "04-score", "05-briefs", "07-ad-copy"]
    missing = [n for n in expected if not (ROOT / "prompts" / f"{n}.md").exists()]
    if missing:
        fail(f"missing prompt files: {', '.join(missing)}")
    else:
        ok(f"all {len(expected)} prompt files present")


def check_higgsfield(cfg):
    section("Higgsfield")
    provider = cfg["images"]["provider"] if cfg else "?"
    print(f"         provider: {provider}   model: {cfg['images'].get('model')}")
    exe = shutil.which(cfg["images"].get("cli", "higgsfield") if cfg else "higgsfield") \
        or shutil.which("higgsfield.cmd")
    if not exe:
        if provider == "higgsfield":
            fail("higgsfield CLI not on PATH but provider is 'higgsfield'",
                 "npm i -g @higgsfield/cli, or set provider: manual")
        else:
            warn("higgsfield CLI not on PATH (fine while provider is 'manual')")
        return
    ok(f"CLI found: {exe}")
    try:
        r = subprocess.run([exe, "account", "--json"],
                           capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            ok("authenticated (account command succeeded)")
            credits = None
            try:
                credits = json.dumps(json.loads(r.stdout))[:200]
            except Exception:
                credits = r.stdout.strip()[:200]
            print(f"         {credits}")
        else:
            fail("CLI is installed but the account call failed",
                 "higgsfield auth login")
    except Exception as e:
        warn(f"could not run the CLI: {e}")


def check_product(cfg, slug):
    section(f"Product: {slug}")
    import yaml
    raw = Path(cfg["paths"]["products"])
    proot = raw if raw.is_absolute() else ROOT / raw
    p = proot / slug
    if not p.exists():
        fail(f"no product folder at {p}")
        return

    links = p / "links.txt"
    if not links.exists():
        fail("links.txt missing", "paste the landing page URL into links.txt")
    else:
        urls = [ln.strip() for ln in links.read_text(encoding="utf-8",
                                                     errors="replace").splitlines()
                if ln.strip() and not ln.startswith("#")
                and ln.strip().startswith("http")
                and "example.com" not in ln]
        if urls:
            ok(f"links.txt: {len(urls)} URL(s)")
            for u in urls:
                print(f"         {u}")
        else:
            fail("links.txt has no real URLs",
                 "paste the landing page URL and delete the example lines")

    refs = [f for f in (p / "reference").glob("*")
            if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}] \
        if (p / "reference").exists() else []
    if len(refs) >= 3:
        ok(f"reference images: {len(refs)}")
    elif refs:
        warn(f"only {len(refs)} reference image(s) — 3–5 gives better consistency")
    else:
        fail("no reference images — image generation can't preserve the product")

    all_imgs = []
    for kind, minimum in (("winners", 1), ("losers", 2)):
        folder = p / kind
        imgs = [f for f in folder.glob("*")
                if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}] \
            if folder.exists() else []
        all_imgs += imgs
        if len(imgs) >= minimum:
            ok(f"{kind}: {len(imgs)} image(s)")
        elif kind == "losers":
            warn(f"{kind}: {len(imgs)} — 2-3 losers roughly doubles the quality "
                 f"of everything downstream")
        else:
            fail(f"{kind}: no images found")

    mcsv = p / "metrics.csv"
    if not mcsv.exists():
        fail("metrics.csv missing",
             "Ads Manager > filter to these ads > Reports > Export CSV")
    else:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import metrics as metrics_mod
            names = [i.name for i in all_imgs]
            data, unmatched, missing = metrics_mod.load(mcsv, names)
            cols = metrics_mod.map_columns(
                next(iter(__import__("csv").DictReader(
                    mcsv.open(encoding="utf-8-sig")))).keys())
            found = [k for k in ("CTR", "CPM", "CVR", "ROAS", "spend") if k in cols]
            gaps = [k for k in ("CTR", "CPM", "CVR", "ROAS", "spend") if k not in cols]
            if data:
                ok(f"metrics.csv matched {len(data)}/{len(names)} images")
                ok(f"columns found: {', '.join(found)}")
            else:
                fail("metrics.csv matched NO images",
                     "name each image file after its Ad name in Ads Manager")
            for k in gaps:
                warn(f"no '{k}' column found in the export — re-export including it")
            for n in unmatched:
                warn(f"export row '{n}' matches no image file")
            for n in missing:
                warn(f"image '{n}' has no row in the export")
        except Exception as e:
            fail(f"metrics.csv could not be read: {e}")

    ident = p / "_derived" / "identity.json"
    if ident.exists():
        try:
            d = json.loads(ident.read_text(encoding="utf-8"))
            ok(f"identified: {d.get('product_name')} / problem '{d.get('problem_slug')}'")
        except Exception:
            warn("_derived/identity.json is unreadable — delete it and rerun")
    else:
        print("         not yet identified — the first run will do it")

    log = p / "log.csv"
    if log.exists():
        n = sum(1 for _ in log.open()) - 1
        ok(f"log.csv exists — {n} creatives logged (round 2+ reads from here)")
    else:
        print("         no log.csv yet — expected before the first run")


# ------------------------------------------------------------------ main

def main():
    print("Creative Studio — setup check")
    print(f"repo: {ROOT}")
    check_python()
    check_key()
    cfg = check_config()
    check_knowledge()
    check_prompts()
    if cfg:
        check_higgsfield(cfg)
    if len(sys.argv) > 1 and cfg:
        check_product(cfg, sys.argv[1])

    print("\n" + "=" * 62)
    if _fails:
        print(f"{len(_fails)} blocking issue(s):")
        for f in _fails:
            print(f"  - {f}")
        print("\nFix these before running the pipeline.")
        sys.exit(1)
    if _warns:
        print(f"No blocking issues. {len(_warns)} thing(s) worth knowing:")
        for w in _warns:
            print(f"  - {w}")
    else:
        print("All checks passed.")


if __name__ == "__main__":
    main()
