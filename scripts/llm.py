"""Anthropic API wrapper: prompt loading, variable injection, JSON extraction."""

import base64
import json
import mimetypes
import os
import re
from pathlib import Path

import yaml
from anthropic import Anthropic

ROOT = Path(__file__).resolve().parent.parent
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text())

_client = None


def get_client() -> Anthropic:
    """Created on first use, not at import — so config checks and dry runs
    don't require a key."""
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit(
                "ANTHROPIC_API_KEY is not set.\n"
                "  PowerShell: [Environment]::SetEnvironmentVariable("
                '"ANTHROPIC_API_KEY","sk-ant-...","User")\n'
                "  Then open a NEW terminal window.")
        _client = Anthropic(api_key=key)
    return _client


def load_prompt(name: str, **vars) -> str:
    """Load prompts/{name}.md and substitute {{var}} placeholders.

    Raises if the prompt still contains an unfilled placeholder — a silent
    {{product_name}} reaching the model is a whole wasted run.
    """
    path = ROOT / "prompts" / f"{name}.md"
    text = path.read_text()
    for key, value in vars.items():
        text = text.replace("{{" + key + "}}", str(value))
    leftover = re.findall(r"\{\{(\w+)\}\}", text)
    if leftover:
        raise ValueError(f"{name}.md has unfilled placeholders: {sorted(set(leftover))}")
    return text


def image_block(path: Path) -> dict:
    media_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    data = base64.standard_b64encode(path.read_bytes()).decode()
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": media_type, "data": data},
    }


def call(stage: str, prompt: str, images: list[Path] | None = None,
         prefill: str | None = None) -> str:
    """Single-turn call. `stage` selects the model from config.yaml."""
    model = CONFIG["models"][stage]

    content: list[dict] = []
    for img in images or []:
        content.append(image_block(img))
        content.append({"type": "text", "text": f"[above image: {img.name}]"})
    content.append({"type": "text", "text": prompt})

    messages = [{"role": "user", "content": content}]
    if prefill:
        messages.append({"role": "assistant", "content": prefill})

    resp = get_client().messages.create(
        model=model,
        max_tokens=CONFIG["max_tokens"],
        messages=messages,
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return (prefill or "") + text


def call_json(stage: str, prompt: str, images: list[Path] | None = None):
    """Call and parse JSON. Prefills '[' or '{' is left to the prompt's schema.

    Prefilling with a fence-free opening bracket is the single most reliable
    way to stop the model wrapping output in prose or ```json fences.
    """
    raw = call(stage, prompt, images=images, prefill="[")
    return _parse_json(raw)


def call_json_obj(stage: str, prompt: str, images: list[Path] | None = None):
    raw = call(stage, prompt, images=images, prefill="{")
    return _parse_json(raw)


def _parse_json(raw: str):
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Salvage the outermost array or object.
        for opener, closer in (("[", "]"), ("{", "}")):
            start, end = cleaned.find(opener), cleaned.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(cleaned[start:end + 1])
                except json.JSONDecodeError:
                    continue
        raise ValueError(f"Could not parse JSON. First 500 chars:\n{cleaned[:500]}")
