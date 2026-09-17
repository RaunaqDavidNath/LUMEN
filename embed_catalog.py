"""
Generate and store embeddings for every asset in the catalog.
Run this once (or re-run whenever catalog_metadata.json changes).

Output: embeddings.json  — { asset_name: [float, float, ...] }

Uses the model named in embedding_config.py (free tier: 5 req/min).
"""

import json
import time
import os
from google import genai
from google.genai import types
from embedding_config import EMBEDDING_MODEL, TASK_TYPE_DOCUMENT

CATALOG_PATH = "catalog_metadata.json"
EMBEDDINGS_PATH = "embeddings.json"
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise SystemExit("Set your key first:  export GEMINI_API_KEY=your_key_here")

client = genai.Client(api_key=API_KEY)


def build_text(name, info):
    """Combine the most meaningful fields into one string to embed."""
    parts = [
        name,
        info.get("glossary_term", ""),
        info.get("description", ""),
        f"Owner: {info.get('owner', '')}",
        "Columns: " + ", ".join(info.get("columns", [])),
    ]
    if info.get("source_tables"):
        parts.append("Built from: " + ", ".join(info["source_tables"]))
    return " | ".join(p for p in parts if p.strip())


def embed(text):
    for attempt in range(5):
        try:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=types.EmbedContentConfig(task_type=TASK_TYPE_DOCUMENT),
            )
            return result.embeddings[0].values
        except Exception as e:
            msg = str(e)
            if "429" in msg or "503" in msg:
                import re
                match = re.search(r"retryDelay.*?(\d+)s", msg)
                wait = int(match.group(1)) + 5 if match else 65
                print(f"  rate limited, waiting {wait}s ...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")


def main():
    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    try:
        with open(EMBEDDINGS_PATH) as f:
            embeddings = json.load(f)
    except FileNotFoundError:
        embeddings = {}

    total = len(catalog)
    for i, (name, info) in enumerate(catalog.items(), 1):
        if name in embeddings:
            print(f"[{i}/{total}] Skipping '{name}' (already embedded)")
            continue
        text = build_text(name, info)
        print(f"[{i}/{total}] Embedding '{name}' ...", end=" ", flush=True)
        embeddings[name] = embed(text)
        print("done")
        time.sleep(13)  # free tier: 5 req/min

    with open(EMBEDDINGS_PATH, "w") as f:
        json.dump(embeddings, f)

    print(f"\nDone! embeddings.json updated ({len(embeddings)} assets).")


if __name__ == "__main__":
    main()
