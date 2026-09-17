import json
import os
import time
from google import genai

CATALOG_PATH = "catalog_metadata.json"
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    raise SystemExit("Set your key first:  export GEMINI_API_KEY=your_key_here")

client = genai.Client(api_key=API_KEY)


def build_prompt(name, info):
    parts = [
        f"You are a data catalog assistant. Given metadata about a database table or view, "
        f"return ONLY a JSON object with exactly these three keys:\n"
        f'  "description"   : one clear sentence explaining what this table/view contains\n'
        f'  "glossary_term" : a short business-friendly name (2-4 words, title case)\n'
        f'  "owner"         : which team would own this data (e.g. "Sales Analytics team")\n\n'
        f"Table/view name : {name}\n"
        f"Type            : {info['type']}\n"
        f"Columns         : {', '.join(info['columns'])}\n"
    ]
    if info.get("source_tables"):
        parts.append(f"Built from      : {', '.join(info['source_tables'])}\n")
    if info.get("sql"):
        sql_preview = info["sql"][:400].replace("\n", " ")
        parts.append(f"SQL (preview)   : {sql_preview}\n")
    parts.append("\nRespond with ONLY the JSON object, no markdown, no explanation.")
    return "".join(parts)


def enrich(name, info):
    prompt = build_prompt(name, info)
    for attempt in range(5):
        try:
            response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
            text = response.text.strip().strip("```json").strip("```").strip()
            return json.loads(text)
        except Exception as e:
            msg = str(e)
            if "429" in msg or "503" in msg:
                # parse suggested retry delay from error, default to 65s
                import re
                match = re.search(r"retryDelay.*?(\d+)s", msg)
                wait = int(match.group(1)) + 5 if match else 65
                print(f"rate limited, waiting {wait}s ...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Max retries exceeded")


def main():
    with open(CATALOG_PATH) as f:
        catalog = json.load(f)

    total = len(catalog)
    for i, (name, info) in enumerate(catalog.items(), 1):
        if info.get("description"):
            print(f"[{i}/{total}] Skipping '{name}' (already done)")
            continue
        print(f"[{i}/{total}] Enriching '{name}' ...", end=" ", flush=True)
        try:
            result = enrich(name, info)
            info["description"] = result.get("description", "")
            info["glossary_term"] = result.get("glossary_term", "")
            # The model is inconsistent about capitalising "Team", which
            # would show the same team twice in the UI owner filter.
            owner = result.get("owner", "")
            info["owner"] = " ".join(w.capitalize() for w in owner.split())
            print(f"done ({result.get('glossary_term', '')})")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(13)  # free tier: 5 req/min → 1 every 13s

    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)

    print(f"\nDone! catalog_metadata.json updated with AI descriptions.")


if __name__ == "__main__":
    main()
