#!/usr/bin/env python3
"""Verify the Higgsfield CLI end to end and dump the raw JSON shapes.

    python scripts/probe_higgsfield.py products/acme-serum/reference/front.jpg

Runs one real generation and prints every response. Two purposes:

1. Confirms the CLI works before you spend a full run finding out it doesn't.
2. Dumps the actual JSON structure. `images.py` locates fields by searching for
   key names rather than by fixed path, which is deliberately forgiving — but
   if it can't find a job id or a media URL, paste this output and the adapter
   can be corrected exactly.

Costs one image's worth of credits.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import images as im


def show(label, value):
    print(f"\n=== {label} " + "=" * (60 - len(label)))
    print(json.dumps(value, indent=2)[:3000] if not isinstance(value, str) else value[:3000])


def main():
    if len(sys.argv) < 2:
        raise SystemExit("usage: probe_higgsfield.py <reference-image>")
    ref = Path(sys.argv[1])
    if not ref.exists():
        raise SystemExit(f"No such file: {ref}")

    print(f"CLI: {im.HF}   model: {im.CONFIG['images']['model']}   "
          f"aspect: {im.CONFIG['images']['aspect_ratio']}")

    show("account", im.hf("account"))
    show("image models", im.hf("model", "list", "--image"))

    up = im.hf("upload", str(ref))
    show("upload response", up)
    upload_id = im._find(up, "upload_id", "id", "uploadId")
    print(f"\n-> upload_id resolved as: {upload_id}")
    if not upload_id:
        raise SystemExit("Could not resolve upload_id — paste the response above.")

    prompt = ("Product photo on a clean bathroom counter, soft morning window "
              "light, shallow depth of field, product centred with clear empty "
              "space above it. No text anywhere in the image.")
    created = im.hf("generate", "create", im.CONFIG["images"]["model"],
                    "--prompt", prompt,
                    "--image", str(upload_id),
                    "--aspect-ratio", im.CONFIG["images"]["aspect_ratio"])
    show("generate create response", created)
    job_id = im._find(created, "job_id", "id", "jobId")
    print(f"\n-> job_id resolved as: {job_id}")
    if not job_id:
        raise SystemExit("Could not resolve job_id — paste the response above.")

    done = im.hf("generate", "wait", str(job_id), timeout=900)
    show("generate wait response", done)
    url = im._find_media_url(done)
    print(f"\n-> media url resolved as: {url}")
    if not url:
        raise SystemExit("Could not resolve media URL — paste the response above.")

    out = Path("probe-output.png")
    im.download(url, out)
    print(f"\nDownloaded -> {out.resolve()}")
    print("\nOpen it and check: is the packaging intact? Label legible? "
          "Proportions right?")


if __name__ == "__main__":
    main()
