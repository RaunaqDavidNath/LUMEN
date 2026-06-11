import json
import math
import os
import streamlit as st

st.set_page_config(page_title="Lumen Catalog", layout="wide", page_icon="💡")

TYPE_BADGE = {"base_table": ("TABLE", "#1565C0"), "view": ("VIEW", "#2e7d32")}


@st.cache_data
def load_catalog():
    with open("catalog_metadata.json") as f:
        return json.load(f)


@st.cache_data
def load_embeddings():
    path = "embeddings.json"
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


@st.cache_data
def build_downstream(catalog_json):
    catalog = json.loads(catalog_json)
    downstream = {name: [] for name in catalog}
    for name, info in catalog.items():
        for src in info.get("source_tables", []):
            if src in downstream:
                downstream[src].append(name)
    return downstream


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def get_query_embedding(query):
    """Embed the search query using Gemini."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        result = client.models.embed_content(model="text-embedding-004", contents=query)
        return result.embeddings[0].values
    except Exception:
        return None


catalog = load_catalog()
embeddings = load_embeddings()
downstream_map = build_downstream(json.dumps(catalog))
has_embeddings = bool(embeddings)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("💡 Lumen")
    st.caption("Active Metadata Catalog")
    st.divider()

    type_filter = st.multiselect(
        "Asset type",
        options=["base_table", "view"],
        default=["base_table", "view"],
        format_func=lambda x: "Base Table" if x == "base_table" else "View",
    )

    all_owners = sorted(set(v["owner"] for v in catalog.values() if v.get("owner")))
    owner_filter = st.multiselect("Owner team", options=all_owners, default=all_owners)

    st.divider()
    total = len(catalog)
    tables = sum(1 for v in catalog.values() if v["type"] == "base_table")
    st.metric("Total assets", total)
    c1, c2 = st.columns(2)
    c1.metric("Tables", tables)
    c2.metric("Views", total - tables)

    if has_embeddings:
        st.divider()
        st.caption("Semantic search ready")

# ── Session state ─────────────────────────────────────────────────────────────
if "selected" not in st.session_state:
    st.session_state.selected = None

# ── Detail view ───────────────────────────────────────────────────────────────
if st.session_state.selected:
    name = st.session_state.selected
    info = catalog[name]
    label, color = TYPE_BADGE.get(info["type"], ("?", "#888"))

    if st.button("← Back to catalog"):
        st.session_state.selected = None
        st.rerun()

    st.markdown(
        f'<span style="background:{color};color:white;padding:3px 10px;'
        f'border-radius:4px;font-size:12px;font-weight:bold">{label}</span>',
        unsafe_allow_html=True,
    )
    st.title(info.get("glossary_term", name))
    st.code(name, language=None)
    st.markdown(info.get("description", ""))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Owner", info.get("owner", "—"))
    c2.metric("Type", label)
    c3.metric("Columns", len(info.get("columns", [])))
    c4.metric("Upstream deps", len(info.get("source_tables", [])))

    st.divider()
    tab1, tab2, tab3 = st.tabs(["Columns & Lineage", "Table Lineage", "SQL"])

    with tab1:
        col_lineage = info.get("column_lineage", {})
        rows = [
            {"Column": col, "Derived from": ", ".join(col_lineage.get(col, [])) or "—"}
            for col in info.get("columns", [])
        ]
        st.table(rows)

    with tab2:
        upstream = info.get("source_tables", [])
        downstream = downstream_map.get(name, [])
        cu, cd = st.columns(2)
        with cu:
            st.markdown("#### Upstream")
            st.caption("This asset reads from:")
            if upstream:
                for t in upstream:
                    u_label, u_color = TYPE_BADGE.get(catalog.get(t, {}).get("type", ""), ("?", "#888"))
                    st.markdown(
                        f'<span style="background:{u_color};color:white;padding:1px 6px;'
                        f'border-radius:3px;font-size:11px">{u_label}</span> `{t}`',
                        unsafe_allow_html=True,
                    )
            else:
                st.info("Raw source table — no upstream dependencies.")
        with cd:
            st.markdown("#### Downstream")
            st.caption("This asset is used by:")
            if downstream:
                for t in downstream:
                    d_label, d_color = TYPE_BADGE.get(catalog.get(t, {}).get("type", ""), ("?", "#888"))
                    st.markdown(
                        f'<span style="background:{d_color};color:white;padding:1px 6px;'
                        f'border-radius:3px;font-size:11px">{d_label}</span> `{t}`',
                        unsafe_allow_html=True,
                    )
            else:
                st.info("Not consumed by any downstream view.")

    with tab3:
        if info.get("sql"):
            sql = info["sql"]
            create_idx = sql.upper().find("CREATE VIEW")
            st.code(sql[create_idx:] if create_idx >= 0 else sql, language="sql")
        else:
            st.info("Raw base table — defined in schema.sql, no transformation SQL.")

    st.stop()

# ── Catalog browse ─────────────────────────────────────────────────────────────
st.title("💡 Lumen Data Catalog")
st.caption("Search and explore your data warehouse assets")

# Search bar + mode toggle on the same row
col_search, col_toggle = st.columns([5, 1])
with col_search:
    search = st.text_input(
        "", placeholder="Search by name, description, column, owner...", label_visibility="collapsed"
    )
with col_toggle:
    semantic_on = st.toggle(
        "Semantic",
        value=False,
        disabled=not has_embeddings,
        help="Search by meaning instead of keywords. Run embed_catalog.py first to enable." if not has_embeddings else "Search by meaning using vector similarity",
    )


def keyword_matches(name, info):
    if info["type"] not in type_filter:
        return False
    if info.get("owner") not in owner_filter:
        return False
    if not search:
        return True
    haystack = " ".join([
        name,
        info.get("description", ""),
        info.get("glossary_term", ""),
        info.get("owner", ""),
        " ".join(info.get("columns", [])),
    ]).lower()
    return search.lower() in haystack


def semantic_results(query):
    """Return assets ranked by cosine similarity to the query embedding."""
    query_vec = get_query_embedding(query)
    if query_vec is None:
        st.warning("GEMINI_API_KEY not set — falling back to keyword search.")
        return {n: i for n, i in catalog.items() if keyword_matches(n, i)}

    scored = []
    for name, vec in embeddings.items():
        info = catalog.get(name)
        if not info:
            continue
        if info["type"] not in type_filter:
            continue
        if info.get("owner") not in owner_filter:
            continue
        score = cosine_similarity(query_vec, vec)
        scored.append((score, name, info))

    scored.sort(reverse=True)
    # Only return assets with meaningful similarity (top results or score > 0.6)
    top = scored[:10]
    return {name: info for _, name, info in top}


if search and semantic_on and has_embeddings:
    results = semantic_results(search)
    st.caption(f"Showing top **{len(results)}** semantic matches for \"{search}\"")
else:
    results = {n: i for n, i in catalog.items() if keyword_matches(n, i)}
    st.caption(f"Showing **{len(results)}** of {len(catalog)} assets")

if not results:
    st.warning("No assets match your search.")
    st.stop()

names = list(results.keys())
COLS = 3
for row_start in range(0, len(names), COLS):
    cols = st.columns(COLS)
    for col_idx, col in enumerate(cols):
        idx = row_start + col_idx
        if idx >= len(names):
            break
        name = names[idx]
        info = results[name]
        label, color = TYPE_BADGE.get(info["type"], ("?", "#888"))

        with col:
            with st.container(border=True):
                st.markdown(
                    f'<span style="background:{color};color:white;padding:2px 8px;'
                    f'border-radius:4px;font-size:11px;font-weight:bold">{label}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**{info.get('glossary_term', name)}**")
                st.caption(f"`{name}`")
                st.markdown(
                    f"<small>{info.get('description', '')}</small>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<small style='color:#888'>Owner: {info.get('owner', '—')}</small>",
                    unsafe_allow_html=True,
                )
                m1, m2, m3 = st.columns(3)
                m1.metric("Cols", len(info.get("columns", [])))
                m2.metric("Up", len(info.get("source_tables", [])))
                m3.metric("Down", len(downstream_map.get(name, [])))
                if st.button("Open →", key=f"open_{name}", use_container_width=True):
                    st.session_state.selected = name
                    st.rerun()
