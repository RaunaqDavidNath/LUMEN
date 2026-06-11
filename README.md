# Lumen — A Mini Active-Metadata Catalog

Lumen is a small-scale version of what Atlan's product does: it takes a set of SQL
transformation queries, automatically extracts how data flows between tables and columns,
enriches every asset with AI-generated descriptions, exposes a search UI, and makes the
whole catalog queryable by an AI agent via MCP.

Built as a portfolio project mapping directly to Atlan's core product concepts.

---

## What it does end-to-end

```
schema.sql + transformations.sql
          │
          ▼
    lumen.db (SQLite)          ← 6 raw tables, 15 derived views
          │
          ▼
  lineage_parser.py            ← sqlglot parses SQL into ASTs
          │                       networkx builds the dependency graph
          ▼
catalog_metadata.json          ← 21 assets: columns, SQL, source tables,
table_lineage.json                column-level lineage (87 nodes, 64 edges)
column_lineage.json
          │
          ▼
  enrich_catalog.py            ← Gemini 2.0 Flash adds to every asset:
          │                       description, glossary term, owner team
          ▼
  Enriched catalog
       /      \
      /        \
     ▼          ▼
  app.py     lumen_mcp.py
 Streamlit    MCP server
   UI         (Claude Desktop)
```

---

## How this maps to Atlan

| Atlan concept | This project |
|---|---|
| Enterprise Data Graph | `table_lineage.json` / `column_lineage.json` |
| Active metadata enrichment | AI-generated descriptions via `enrich_catalog.py` |
| Business Glossary | `glossary_term` field on every catalog asset |
| Data ownership | `owner` field auto-assigned per asset |
| Data Marketplace / search | Streamlit catalog UI (`app.py`) |
| Context layer for AI agents | MCP server (`lumen_mcp.py`) wired into Claude Desktop |
| Semantic search | Embedding-based search via Gemini embeddings |

---

## Project structure

```
files/
├── schema.sql               # Raw table definitions (the "source layer")
├── setup_db.py              # Creates lumen.db with sample e-commerce data
├── transformations.sql      # 15 derived views: staging → fact/dim → mart
├── lineage_parser.py        # SQL → lineage graph (sqlglot + networkx)
├── visualize_lineage.py     # Renders lineage_graph.html (pyvis)
├── enrich_catalog.py        # AI enrichment via Gemini 2.0 Flash API
├── app.py                   # Streamlit catalog search UI
├── lumen_mcp.py             # MCP server for Claude Desktop
├── catalog_metadata.json    # 21 assets — all AI-enriched
├── table_lineage.json       # Table-level graph (21 nodes, 20 edges)
├── column_lineage.json      # Column-level graph (87 nodes, 64 edges)
├── lineage_graph.html       # Interactive lineage visualization (open in browser)
└── requirements.txt
```

---

## The data model

An e-commerce warehouse with three transformation layers:

**Base tables (6):** `customers`, `orders`, `order_items`, `products`, `categories`, `suppliers`

**Staging layer:** Light cleanup — `stg_orders` drops cancelled orders, `stg_order_items`
pre-computes `line_total = quantity × unit_price`

**Fact / dimension layer:** Business-friendly joins — `dim_customers` adds customer segments,
`dim_products` denormalizes category + supplier, `fct_order_revenue` aggregates to order-level revenue

**Mart layer:** Analysis-ready aggregations — `customer_lifetime_value`, `top_customers`,
`repeat_customers`, `monthly_revenue`, `category_revenue`, `supplier_performance`, and more

---

## How to run it

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Build the database and parse lineage
```bash
python3 setup_db.py          # creates lumen.db with sample data
python3 lineage_parser.py    # parses SQL → catalog_metadata.json, table/column lineage
python3 visualize_lineage.py # generates lineage_graph.html
```

Open `lineage_graph.html` in a browser to explore the lineage graph interactively.

### 3. Enrich the catalog with AI descriptions
```bash
export GEMINI_API_KEY=your_key_here
python3 enrich_catalog.py
```

This calls Gemini 2.0 Flash for each of the 21 assets and writes `description`,
`glossary_term`, and `owner` back into `catalog_metadata.json`. Handles free-tier
rate limits automatically (5 req/min).

### 4. Launch the Streamlit UI
```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Features:
- Full-text search across names, descriptions, columns, and owners
- Filter by asset type (Table / View) and owner team
- Card grid with type badges and upstream/downstream counts
- Detail view with column lineage table, table lineage, and SQL

### 5. Connect to Claude Desktop (MCP)
Add this to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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
- *"Search the catalog for anything related to revenue"*
- *"Show me the full lineage of `fct_order_revenue`"*

---

## MCP tools

| Tool | Description |
|---|---|
| `list_assets()` | Overview of all 21 tables and views |
| `search_catalog(query)` | Keyword search across all metadata fields |
| `get_asset_details(name)` | Full metadata: columns, lineage, SQL, owner |
| `get_lineage(name)` | Upstream + downstream + 2-hop grandparent sources |

---

## For an NLP person: the translation layer

If you're coming from conversational AI / NLP, here's how the concepts map:

**Lineage graph ≈ dependency parse tree.**
In NLP, a dependency parse turns a sentence into nodes (tokens) and directed edges
(grammatical relations). Here, nodes are tables/columns and edges mean "this data feeds
into that". Same directed graph, different domain.

**`sqlglot` ≈ a syntactic parser for SQL.**
Just like a dependency parser turns a sentence string into an AST you can walk, `sqlglot`
turns SQL into an AST. We walk that AST to extract which tables each query reads from.

**Graph traversal = "context retrieval".**
Questions like "what does `customer_lifetime_value` ultimately depend on?" are just
`nx.ancestors()` calls — the same mental model as retrieving relevant context for an LLM,
except the retrieval is graph traversal instead of vector similarity.

**Active metadata ≈ a self-updating knowledge base.**
Instead of a human writing "this column means X", the system generates that description
automatically from schema + lineage + SQL — then stores it back into the catalog. Same idea
as bootstrapping a knowledge base from raw text instead of hand-curating every entry.

**Semantic search ≈ what you already know.**
Embed each asset's description + name into a vector. At query time, embed the search query
and find the closest assets by cosine similarity. Exact same mechanism as dense retrieval
in RAG — just applied to a metadata catalog instead of documents.

---

## Tech stack

| Layer | Library |
|---|---|
| SQL parsing | `sqlglot` |
| Graph building + traversal | `networkx` |
| Graph visualization | `pyvis` |
| Database | SQLite (via `sqlite3`) |
| AI enrichment | Gemini 2.0 Flash (`google-genai`) |
| Semantic search | Gemini `text-embedding-004` |
| UI | `streamlit` |
| AI agent interface | `mcp` (FastMCP) |
