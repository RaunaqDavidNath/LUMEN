"""
visualize_lineage.py
---------------------
Loads table_lineage.json (produced by lineage_parser.py) and renders it as
an interactive HTML graph using pyvis. Open lineage_graph.html in a browser
afterwards — you can drag nodes, zoom, and hover for details.

Color coding:
  - base tables (raw data)        : grey
  - staging views (stg_*)         : blue
  - fact/dim views (fct_*, dim_*) : orange
  - mart views (everything else)  : green
"""

import json
import os
import networkx as nx
from pyvis.network import Network

BASE_DIR = os.path.dirname(__file__)


def classify(name, node_type):
    if node_type == "base_table":
        return "Raw table", "#8a8d91"
    if name.startswith("stg_"):
        return "Staging", "#4f8ef7"
    if name.startswith(("fct_", "dim_")):
        return "Fact/Dimension", "#f5a623"
    return "Mart (analytics)", "#34a853"


def main():
    with open(os.path.join(BASE_DIR, "table_lineage.json")) as f:
        data = json.load(f)

    G = nx.node_link_graph(data, edges="edges")

    net = Network(height="800px", width="100%", directed=True,
                   bgcolor="#0e1117", font_color="white",
                   cdn_resources="in_line")
    net.barnes_hut(gravity=-25000, central_gravity=0.3, spring_length=150)

    legend_added = set()
    for node, attrs in G.nodes(data=True):
        label, color = classify(node, attrs.get("type"))
        legend_added.add((label, color))
        net.add_node(node, label=node, color=color, title=label,
                      shape="box", font={"size": 14})

    for src, dst in G.edges():
        net.add_edge(src, dst, color="#555555", arrows="to")

    out_path = os.path.join(BASE_DIR, "lineage_graph.html")
    net.write_html(out_path, notebook=False, open_browser=False)

    print(f"Wrote {out_path}")
    print("\nLegend:")
    for label, color in sorted(legend_added):
        print(f"  {color}  {label}")


if __name__ == "__main__":
    main()
