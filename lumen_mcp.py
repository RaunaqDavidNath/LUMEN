"""
Lumen MCP Server. Exposes the Lumen data catalog to Claude Desktop.

Tools:
  list_assets          - overview of every table/view in the catalog
  search_catalog       - keyword search across names, descriptions, columns, owners
  get_asset_details    - full metadata for one asset (columns, lineage, SQL, owner)
  get_lineage          - upstream + downstream lineage for any asset
  semantic_search      - embedding-based search by meaning (requires embeddings.json)
"""

import json
import math
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

CATALOG_PATH = Path(__file__).parent / "catalog_metadata.json"
EMBEDDINGS_PATH = Path(__file__).parent / "embeddings.json"

mcp = FastMCP("Lumen Catalog")


def _load():
    with open(CATALOG_PATH) as f:
        return json.load(f)


def _downstream(catalog):
    ds = {name: [] for name in catalog}
    for name, info in catalog.items():
        for src in info.get("source_tables", []):
            if src in ds:
                ds[src].append(name)
    return ds


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_assets() -> str:
    """List every table and view in the Lumen catalog with a one-line summary."""
    catalog = _load()
    lines = ["# Lumen Catalog - All Assets\n"]
    tables = [(n, i) for n, i in catalog.items() if i["type"] == "base_table"]
    views  = [(n, i) for n, i in catalog.items() if i["type"] == "view"]

    lines.append(f"**{len(tables)} base tables, {len(views)} views ({len(catalog)} total)**\n")

    lines.append("\n## Base Tables")
    for name, info in tables:
        lines.append(f"- `{name}` | {info.get('glossary_term', '')} | Owner: {info.get('owner', 'unknown')} | {len(info.get('columns', []))} columns")

    lines.append("\n## Views")
    for name, info in views:
        ups = ", ".join(info.get("source_tables", [])) or "none"
        lines.append(f"- `{name}` | {info.get('glossary_term', '')} | Owner: {info.get('owner', 'unknown')} | Built from: {ups}")

    return "\n".join(lines)


@mcp.tool()
def search_catalog(query: str) -> str:
    """
    Search the catalog by keyword. Matches against asset name, description,
    glossary term, column names, and owner team.

    Args:
        query: The search term (e.g. 'revenue', 'customer segment', 'supplier')
    """
    catalog = _load()
    q = query.lower()
    results = []

    for name, info in catalog.items():
        haystack = " ".join([
            name,
            info.get("description", ""),
            info.get("glossary_term", ""),
            info.get("owner", ""),
            " ".join(info.get("columns", [])),
        ]).lower()
        if q in haystack:
            results.append((name, info))

    if not results:
        return f"No assets found matching '{query}'."

    lines = [f"# Search results for '{query}' ({len(results)} match(es))\n"]
    for name, info in results:
        kind = "TABLE" if info["type"] == "base_table" else "VIEW"
        lines.append(f"## `{name}` [{kind}]")
        lines.append(f"**{info.get('glossary_term', '')}** | Owner: {info.get('owner', 'unknown')}")
        lines.append(info.get("description", ""))
        lines.append(f"Columns: {', '.join(info.get('columns', []))}\n")

    return "\n".join(lines)


@mcp.tool()
def get_asset_details(name: str) -> str:
    """
    Return full metadata for a specific table or view: description, owner,
    all columns with their column-level lineage, and the SQL definition.

    Args:
        name: Exact table/view name (e.g. 'customer_lifetime_value')
    """
    catalog = _load()
    if name not in catalog:
        close = [n for n in catalog if name.lower() in n.lower()]
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return f"Asset '{name}' not found.{hint}"

    info = catalog[name]
    kind = "Base Table" if info["type"] == "base_table" else "View"
    col_lineage = info.get("column_lineage", {})

    lines = [
        f"# {info.get('glossary_term', name)} (`{name}`)",
        f"**Type:** {kind}  |  **Owner:** {info.get('owner', 'unknown')}",
        f"\n{info.get('description', '')}\n",
        "## Columns",
    ]

    for col in info.get("columns", []):
        sources = col_lineage.get(col, [])
        src_str = f" ← {', '.join(sources)}" if sources else ""
        lines.append(f"- `{col}`{src_str}")

    if info.get("source_tables"):
        lines.append(f"\n**Built from:** {', '.join(info['source_tables'])}")

    if info.get("sql"):
        sql = info["sql"]
        create_idx = sql.upper().find("CREATE VIEW")
        if create_idx >= 0:
            sql = sql[create_idx:]
        lines.append(f"\n## SQL\n```sql\n{sql}\n```")
    else:
        lines.append("\n_Raw base table with no transformation SQL._")

    return "\n".join(lines)


@mcp.tool()
def get_lineage(name: str) -> str:
    """
    Show the full upstream and downstream lineage for a table or view.
    Upstream = what this asset reads from. Downstream = what reads from this asset.

    Args:
        name: Exact table/view name (e.g. 'fct_order_revenue')
    """
    catalog = _load()
    if name not in catalog:
        close = [n for n in catalog if name.lower() in n.lower()]
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        return f"Asset '{name}' not found.{hint}"

    downstream_map = _downstream(catalog)
    info = catalog[name]
    upstream = info.get("source_tables", [])
    downstream = downstream_map.get(name, [])

    lines = [f"# Lineage for `{name}`\n"]

    lines.append("## Upstream (this asset reads from)")
    if upstream:
        for t in upstream:
            t_info = catalog.get(t, {})
            kind = "TABLE" if t_info.get("type") == "base_table" else "VIEW"
            desc = t_info.get("glossary_term") or t_info.get("description", "")
            lines.append(f"- `{t}` [{kind}] - {desc}")
    else:
        lines.append("- _None, this is a raw source table_")

    lines.append("\n## Downstream (assets that read from this)")
    if downstream:
        for t in downstream:
            t_info = catalog.get(t, {})
            kind = "TABLE" if t_info.get("type") == "base_table" else "VIEW"
            desc = t_info.get("glossary_term") or t_info.get("description", "")
            lines.append(f"- `{t}` [{kind}] - {desc}")
    else:
        lines.append("- _None, this asset is not used by any downstream view_")

    # Multi-hop: show grandparents too
    if upstream:
        grandparents = []
        for t in upstream:
            for gp in catalog.get(t, {}).get("source_tables", []):
                if gp not in grandparents and gp != name:
                    grandparents.append(gp)
        if grandparents:
            lines.append("\n## Grandparent sources (2 hops upstream)")
            for gp in grandparents:
                lines.append(f"- `{gp}`")

    return "\n".join(lines)


@mcp.tool()
def semantic_search(query: str, top_k: int = 5) -> str:
    """
    Search the catalog by meaning using vector similarity. Finds relevant assets
    even if the exact words aren't in the name or description.

    Requires embeddings.json to exist (run embed_catalog.py first).

    Args:
        query: A natural-language description of what you're looking for
               (e.g. 'tables about customer purchasing behaviour')
        top_k: How many results to return (default 5)
    """
    if not EMBEDDINGS_PATH.exists():
        return (
            "embeddings.json not found. Run embed_catalog.py first to generate embeddings:\n"
            "  export GEMINI_API_KEY=your_key\n"
            "  python3 embed_catalog.py"
        )

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return "GEMINI_API_KEY environment variable not set. Cannot embed the query."

    try:
        from google import genai
        from google.genai import types
        from embedding_config import EMBEDDING_MODEL, TASK_TYPE_QUERY
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=query,
            config=types.EmbedContentConfig(task_type=TASK_TYPE_QUERY),
        )
        query_vec = result.embeddings[0].values
    except Exception as e:
        return f"Failed to embed query: {e}"

    with open(EMBEDDINGS_PATH) as f:
        embeddings = json.load(f)
    catalog = _load()

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    scored = sorted(
        [(cosine(query_vec, vec), name) for name, vec in embeddings.items()],
        reverse=True,
    )[:top_k]

    lines = [f"# Semantic search for '{query}' (top {top_k} results)\n"]
    for rank, (score, name) in enumerate(scored, 1):
        info = catalog.get(name, {})
        kind = "TABLE" if info.get("type") == "base_table" else "VIEW"
        lines.append(f"## {rank}. `{name}` [{kind}]  (similarity: {score:.3f})")
        lines.append(f"**{info.get('glossary_term', '')}** | Owner: {info.get('owner', 'unknown')}")
        lines.append(info.get("description", ""))
        lines.append(f"Columns: {', '.join(info.get('columns', []))}\n")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
