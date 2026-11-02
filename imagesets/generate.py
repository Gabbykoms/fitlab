"""Generate an image set through OpenRouter's Image API and write a manifest.

    python3 generate.py prompts.json --out imagesets/<set>              # needs OPENROUTER_API_KEY
    python3 generate.py prompts.json --only occasion-01 --out /tmp/seed-check
    python3 generate.py prompts.json --only occasion-01 \\
        --model google/gemini-3.1-flash-lite-image --out /tmp/compare

One billed call per prompt. The manifest records prompt, seed, model, media type, file,
seconds and the cost from the reply, so the critic and the checker never guess what was asked.
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "black-forest-labs/flux.2-klein-4b"
EXTENSIONS = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def generate_one(client, model: str, prompt: str, seed: int, aspect_ratio: str) -> dict:
    """One Image API call (POST /api/v1/images). Returns the bytes, media type and billed cost."""
    reply = client.images.generate(model=model, prompt=prompt, aspect_ratio=aspect_ratio, seed=seed)
    item = reply.data[0]
    return {"bytes": base64.b64decode(item.b64_json), "media_type": item.media_type,
            "cost": getattr(reply.usage, "cost", None)}


def manifest_entry(prompt: dict, model: str, aspect_ratio: str, file: str, result: dict, seconds: float) -> dict:
    return {**prompt, "model": model, "aspect_ratio": aspect_ratio, "file": file,
            "media_type": result["media_type"], "cost": result["cost"], "seconds": round(seconds, 1)}


def write_manifest(out: Path, entries: list[dict]) -> None:
    (out / "manifest.json").write_text(json.dumps(entries, indent=2) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prompts", type=Path)
    ap.add_argument("--out", type=Path, required=True, help="the set's folder, e.g. imagesets/<set>")
    ap.add_argument("--model", default=os.environ.get("IMAGE_MODEL", DEFAULT_MODEL))
    ap.add_argument("--aspect-ratio", default="3:4")
    ap.add_argument("--only", help="generate just the prompt with this name")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY is not set; image generation is a billed call. Nothing generated.")
    from openrouter import OpenRouter          # imported here so the no-key path never needs it

    prompts = json.loads(args.prompts.read_text())
    if args.only:
        prompts = [p for p in prompts if p["name"] == args.only]
        if not prompts:
            sys.exit(f"No prompt named {args.only!r} in {args.prompts}.")
    client = OpenRouter(api_key=key)
    args.out.mkdir(parents=True, exist_ok=True)
    entries, total = [], 0.0
    for prompt in prompts:
        started = time.time()
        try:
            result = generate_one(client, args.model, prompt["prompt"], prompt["seed"], args.aspect_ratio)
        except Exception as exc:                    # any SDK or network error: keep what was already generated
            write_manifest(args.out, entries)
            status = getattr(exc, "status_code", None)  # never print the error body (CLAUDE.md)
            sys.exit(f"{prompt['name']}: image request failed ({type(exc).__name__}"
                     f"{f', HTTP {status}' if status else ''}). {len(entries)} image(s) kept in {args.out}.")
        path = args.out / f"{prompt['name']}.{EXTENSIONS.get(result['media_type'], 'bin')}"
        path.write_bytes(result["bytes"])
        entry = manifest_entry(prompt, args.model, args.aspect_ratio, path.name, result, time.time() - started)
        entries.append(entry)
        total += result["cost"] or 0.0
        print(f"{path}  {result['media_type']}  seed={prompt['seed']}  ${result['cost']}  {entry['seconds']}s")
    write_manifest(args.out, entries)
    print(f"{len(entries)} image(s), ${total:.4f} total, manifest in {args.out / 'manifest.json'}")


if __name__ == "__main__":
    main()
