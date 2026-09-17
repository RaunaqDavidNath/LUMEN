"""
lineage_parser.py
------------------
Parses schema.sql (base tables) and transformations.sql (derived views),
then builds two lineage graphs using networkx:

  1. table_graph  : node = table/view name
                     edge  = "this table's data flows into that table"
  2. column_graph : node = "table.column"
                     edge  = "this column's data flows into that column"

Both graphs are saved as JSON (node-link format) so later steps (Claude
description generation, Streamlit UI) can load them without re-parsing SQL.

We also build catalog_metadata.json — a dict of every table/view with its
type, columns, and (for views) the SQL definition + direct upstream tables.
This is the raw material that Claude will later turn into human-readable
descriptions.
"""

import json
import os
import sqlglot
from sqlglot import exp
import networkx as nx

BASE_DIR = os.path.dirname(__file__)
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")
TRANSFORM_PATH = os.path.join(BASE_DIR, "transformations.sql")
CATALOG_PATH = os.path.join(BASE_DIR, "catalog_metadata.json")

# Fields written by enrich_catalog.py, not by this parser. Re-parsing SQL must
# not throw them away, or every re-run would cost a full round of API calls.
ENRICHED_FIELDS = ("description", "glossary_term", "owner")

DIALECT = "sqlite"


def parse_schema(path):
    """Extract base table definitions: {table_name: {type, columns}}"""
    sql = open(path).read()
    metadata = {}
    for stmt in sqlglot.parse(sql, dialect=DIALECT):
        if not isinstance(stmt, exp.Create):
            continue
        table_name = stmt.this.this.name  # Schema -> Table -> name
        columns = []
        for col_def in stmt.find_all(exp.ColumnDef):
            columns.append(col_def.this.name)
        metadata[table_name] = {
            "type": "base_table",
            "columns": columns,
            "sql": None,
            "source_tables": [],
        }
    return metadata


def alias_map_for(select_expr):
    """Map table aliases (or table names if unaliased) -> real table names."""
    mapping = {}
    for t in select_expr.find_all(exp.Table):
        mapping[t.alias_or_name] = t.name
    return mapping


def resolve_table(column, alias_map, source_tables):
    """Figure out which source table a (possibly unqualified) column belongs to."""
    if column.table:
        return alias_map.get(column.table, column.table)
    if len(source_tables) == 1:
        return source_tables[0]
    return None  # ambiguous — would need schema-aware resolution


def parse_transformations(path):
    """Extract view definitions: {view_name: {type, columns, sql, source_tables, column_lineage}}"""
    sql = open(path).read()
    metadata = {}

    for stmt in sqlglot.parse(sql, dialect=DIALECT):
        if not isinstance(stmt, exp.Create) or stmt.kind != "VIEW":
            continue

        view_name = stmt.this.name
        select_expr = stmt.expression

        alias_map = alias_map_for(select_expr)
        source_tables = sorted(set(alias_map.values()))

        output_columns = []
        column_lineage = {}  # output_col -> [ "source_table.source_col", ... ]

        for proj in select_expr.expressions:
            out_name = proj.alias_or_name
            output_columns.append(out_name)

            sources = []
            for c in proj.find_all(exp.Column):
                src_table = resolve_table(c, alias_map, source_tables)
                if src_table:
                    sources.append(f"{src_table}.{c.name}")
            column_lineage[out_name] = sorted(set(sources))

        metadata[view_name] = {
            "type": "view",
            "columns": output_columns,
            "sql": stmt.sql(dialect=DIALECT, pretty=True),
            "source_tables": source_tables,
            "column_lineage": column_lineage,
        }

    return metadata


def merge_enrichment(catalog, path):
    """Copy AI-generated fields from an existing catalog file onto a fresh parse.

    The parser rebuilds structure (columns, SQL, lineage) from the .sql files,
    so anything it does not know about has to be carried over by hand.
    """
    try:
        with open(path) as f:
            previous = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0

    carried = 0
    for name, info in catalog.items():
        old = previous.get(name)
        if not old:
            continue
        for field in ENRICHED_FIELDS:
            if old.get(field) and not info.get(field):
                info[field] = old[field]
                carried += 1
    return carried


def build_graphs(catalog):
    table_graph = nx.DiGraph()
    column_graph = nx.DiGraph()

    # Add every table/view as a node first (so isolated nodes still appear)
    for name, info in catalog.items():
        table_graph.add_node(name, type=info["type"])
        for col in info["columns"]:
            column_graph.add_node(f"{name}.{col}", table=name, type=info["type"])

    # Edges: source -> target (data flows from upstream to downstream)
    for name, info in catalog.items():
        for src in info.get("source_tables", []):
            table_graph.add_edge(src, name)

        for out_col, sources in info.get("column_lineage", {}).items():
            target_node = f"{name}.{out_col}"
            for src in sources:
                if src in column_graph:
                    column_graph.add_edge(src, target_node)

    return table_graph, column_graph


def main():
    base_meta = parse_schema(SCHEMA_PATH)
    view_meta = parse_transformations(TRANSFORM_PATH)

    catalog = {**base_meta, **view_meta}
    carried = merge_enrichment(catalog, CATALOG_PATH)
    table_graph, column_graph = build_graphs(catalog)

    # Save catalog metadata, keeping any AI enrichment from a previous run
    with open(CATALOG_PATH, "w") as f:
        json.dump(catalog, f, indent=2)

    # Save graphs in node-link JSON format
    with open(os.path.join(BASE_DIR, "table_lineage.json"), "w") as f:
        json.dump(nx.node_link_data(table_graph, edges="edges"), f, indent=2)

    with open(os.path.join(BASE_DIR, "column_lineage.json"), "w") as f:
        json.dump(nx.node_link_data(column_graph, edges="edges"), f, indent=2)

    # ---- Summary ----
    print(f"Catalog: {len(catalog)} tables/views "
          f"({len(base_meta)} base tables, {len(view_meta)} derived views)")
    print(f"Table-level graph: {table_graph.number_of_nodes()} nodes, "
          f"{table_graph.number_of_edges()} edges")
    print(f"Column-level graph: {column_graph.number_of_nodes()} nodes, "
          f"{column_graph.number_of_edges()} edges")
    if carried:
        print(f"Kept {carried} AI-enriched fields from the previous catalog")

    print("\nExample — full lineage of 'customer_lifetime_value':")
    for ancestor in nx.ancestors(table_graph, "customer_lifetime_value"):
        print(f"  {ancestor} -> ... -> customer_lifetime_value")

    print("\nExample — what breaks if 'orders' changes (downstream impact):")
    for descendant in nx.descendants(table_graph, "orders"):
        print(f"  orders -> ... -> {descendant}")


if __name__ == "__main__":
    main()
