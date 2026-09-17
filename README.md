# Lumen - Active Metadata Catalog

Lumen is a lightweight active-metadata catalog that ingests a SQL-based data warehouse, automatically extracts table and column-level lineage, enriches every asset with AI-generated descriptions, and exposes the catalog through a search UI and an MCP server for AI agents.

---

## Features

- **Automatic lineage extraction.** Parses SQL views to build a full dependency graph at both table and column level.
- **AI enrichment.** Generates a plain-English description, business glossary term, and owner team for every asset.
- **Semantic search.** Searches by meaning using vector embeddings, not just keywords.
- **Streamlit UI.** Browse, filter, and search the catalog with a clean card-based interface.
- **MCP server.** Exposes the catalog as tools so an AI agent can query it conversationally.

---

## Architecture

```
schema.sql + transformations.sql
          │
          ▼
    lumen.db (SQLite)          ← 6 raw tables, 15 derived views
          │
          ▼
  lineage_parser.py            ← builds table + column lineage graphs
          │
          ▼
catalog_metadata.json          ← 21 assets catalogued
table_lineage.json             ← 21 nodes, 20 edges
column_lineage.json            ← 87 nodes, 64 edges
          │
          ▼
  enrich_catalog.py            ← AI descriptions, glossary terms, owners
          │
          ▼
       /      \
      ▼        ▼
   app.py   lumen_mcp.py
  Streamlit   MCP server
    UI       (Claude Desktop)
```

---

## Data model

An e-commerce warehouse with three transformation layers.

**Base tables (6):** `customers`, `orders`, `order_items`, `products`, `categories`, `suppliers`

**Staging layer:** Light cleanup that drops cancelled orders and pre-computes line-level revenue

**Fact / Dimension layer:** `dim_customers`, `dim_products`, `fct_order_revenue`

**Mart layer:** `customer_lifetime_value`, `top_customers`, `repeat_customers`, `monthly_revenue`, `category_revenue`, `supplier_performance`, and more

---

## Project structure

```
files/
├── schema.sql               # Raw table definitions
├── setup_db.py              # Creates lumen.db with sample data
├── transformations.sql      # 15 derived views
├── lineage_parser.py        # SQL → lineage graphs (sqlglot + networkx)
├── visualize_lineage.py     # Renders lineage_graph.html (pyvis)
├── enrich_catalog.py        # AI enrichment via Gemini 2.0 Flash
├── embed_catalog.py         # Generates embeddings for semantic search
├── embedding_config.py      # Shared embedding model name and task types
├── app.py                   # Streamlit catalog UI (Catalog and Help sections)
├── .streamlit/config.toml   # Light and dark UI themes
├── lumen_mcp.py             # MCP server for Claude Desktop
├── catalog_metadata.json    # 21 assets, all AI-enriched
├── table_lineage.json       # Table-level lineage graph
├── column_lineage.json      # Column-level lineage graph
├── lineage_graph.html       # Interactive lineage visualization
├── embeddings.json          # Vector embeddings (generated, git-ignored)
└── requirements.txt
```

---

## Getting started

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Build the database and parse lineage
```bash
python3 setup_db.py
python3 lineage_parser.py
python3 visualize_lineage.py
```

Open `lineage_graph.html` in a browser to explore the lineage graph interactively.

Re-running `lineage_parser.py` later is safe. It rebuilds structure and lineage from
the `.sql` files while keeping any AI enrichment already in `catalog_metadata.json`.

### 3. Enrich the catalog with AI descriptions
```bash
export GEMINI_API_KEY=your_key_here
python3 enrich_catalog.py
```

Generates `description`, `glossary_term`, and `owner` for all 21 assets. Handles free-tier rate limits automatically.

### 4. Generate embeddings for semantic search
```bash
python3 embed_catalog.py
```

### 5. Launch the Streamlit UI
```bash
streamlit run app.py
```

Opens at `http://localhost:8501`.

The sidebar switches between two sections. **Catalog** is the searchable grid of
assets, with filters for asset type and owning team. **Help** explains how to use
it step by step.

**Light and dark themes** are both defined in `.streamlit/config.toml`. Switch
between them from the menu at the top right of the app, under Settings then
Appearance; by default it follows your operating system. All text in both
themes meets the WCAG AA contrast standard.

Use the **Semantic** switch next to the search box to match on meaning instead of
exact words. Semantic results show a match percentage, and anything below a
similarity of 0.57 is discarded so an unrelated query returns nothing rather than
a page of weak matches.

### 6. Connect to Claude Desktop
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lumen": {
      "command": "python3",
      "args": ["/absolute/path/to/files/lumen_mcp.py"]
    }
  }
}
```

Restart Claude Desktop. You can then ask it things like:
- *"What does `customer_lifetime_value` depend on?"*
- *"Find all assets related to revenue"*
- *"Show me the full lineage of `fct_order_revenue`"*

---

## Deploying to Cloud Run

The app is packaged by the `Dockerfile`. It listens on the port Cloud Run
provides and binds to `0.0.0.0`, and `catalog_metadata.json` plus
`embeddings.json` are both in the repository, so the image is self contained.
`lumen.db` is not needed at run time.

Semantic search calls Gemini for every query, so the deployed service needs
`GEMINI_API_KEY`. Keep it in Secret Manager rather than passing it as a plain
environment variable. Without the key the app still runs and falls back to
keyword search.

```bash
# one time setup
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com secretmanager.googleapis.com

printf %s "$GEMINI_API_KEY" | gcloud secrets create gemini-api-key \
    --data-file=- --replication-policy=automatic

# build from source and deploy
gcloud run deploy lumen-catalog \
    --source . \
    --region asia-south1 \
    --allow-unauthenticated \
    --memory 1Gi \
    --max-instances 3 \
    --session-affinity \
    --set-secrets GEMINI_API_KEY=gemini-api-key:latest
```

`--session-affinity` matters: Streamlit holds an open websocket, so a reconnect
needs to reach the same instance. `--max-instances` caps what the service can
ever cost.

---

## MCP tools

| Tool | Description |
|---|---|
| `list_assets()` | Overview of all 21 tables and views |
| `search_catalog(query)` | Keyword search across all metadata fields |
| `get_asset_details(name)` | Columns, lineage, SQL and owner for one asset |
| `get_lineage(name)` | Upstream + downstream + 2-hop sources |
| `semantic_search(query, top_k)` | Vector similarity search over catalog embeddings |

---

## Tech stack

| Layer | Library |
|---|---|
| SQL parsing | `sqlglot` |
| Graph building | `networkx` |
| Graph visualization | `pyvis` |
| Database | SQLite |
| AI enrichment | Gemini 2.0 Flash |
| Semantic search | Gemini `gemini-embedding-001` |
| UI | Streamlit |
| AI agent interface | FastMCP |
| Gemini client | google-genai |
