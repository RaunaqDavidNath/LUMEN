"""
Lumen catalog UI.

Two sections, chosen from the sidebar:
  Catalog - a filterable grid of every asset, and a detail page for one asset
  Help    - how to operate the catalog

Run with:  streamlit run app.py
"""

import json
import math
import os
from pathlib import Path
import streamlit as st

# Resolve data files next to this script, not against the current working
# directory, so the app also runs when launched from elsewhere (e.g. a container).
BASE_DIR = Path(__file__).parent

st.set_page_config(page_title="Lumen Catalog", layout="wide")

# --- Palette ----------------------------------------------------------------
# Navy and teal, both desaturated, in a light and a dark variant. The reader
# switches theme from the app menu at the top right (Settings, then
# Appearance); Streamlit themes its own widgets from .streamlit/config.toml
# and we match the cards and badges to whichever theme is showing.
#
# The dark badge colours are lifted a little so white badge text still has
# enough contrast, and the dark accent is lightened because it is used as
# text on a dark background rather than as a fill.
PALETTES = {
    "light": {
        "ink": "#1A2332",
        "muted": "#5F6F81",
        "border": "#DFE5EC",
        "badge_table": "#31567A",
        "badge_view": "#2E6F5E",
        "accent": "#31567A",
    },
    "dark": {
        "ink": "#E3E9F0",
        "muted": "#94A3B4",
        "border": "#2A3744",
        "badge_table": "#3E6B99",
        "badge_view": "#347C66",
        "accent": "#8FBCE4",
    },
}


def active_palette():
    """Colours for the theme the browser is currently showing.

    st.context.theme.type is "light" or "dark", and is None when there is no
    browser attached (for example under Streamlit's test harness), so light
    is the fallback.
    """
    try:
        theme = st.context.theme.type or "light"
    except Exception:
        theme = "light"
    return PALETTES.get(theme, PALETTES["light"])


COLOURS = active_palette()
INK = COLOURS["ink"]
MUTED = COLOURS["muted"]
BORDER = COLOURS["border"]
ACCENT = COLOURS["accent"]

# Asset type -> (badge text, badge colour)
TYPE_STYLE = {
    "base_table": ("Table", COLOURS["badge_table"]),
    "view": ("View", COLOURS["badge_view"]),
}

# Semantic matches weaker than this are dropped, so an unrelated query
# returns nothing instead of a page of confident looking cards.
#
# Measured against this catalog: on-topic queries score 0.60 to 0.73, while
# deliberately unrelated ones ("recipe for chocolate cake") top out at 0.55.
# 0.57 sits in that gap. Re-check it if the catalog or the embedding model
# changes, since the numbers are specific to both.
MIN_SIMILARITY = 0.57
MAX_SEMANTIC_RESULTS = 10

# Descriptions are trimmed to keep every card the same height.
CARD_DESCRIPTION_LIMIT = 115

CSS = """
<style>
  .block-container { padding-top: 2.4rem; max-width: 1320px; }

  .lumen-brand { font-size: 19px; font-weight: 700; color: __INK__;
                 letter-spacing: -0.01em; margin-bottom: 1px; }
  .lumen-brand-sub { font-size: 11px; color: __MUTED__;
                     text-transform: uppercase; letter-spacing: 0.09em; }

  .lumen-badge { display: inline-block; padding: 2px 8px; border-radius: 3px;
                 font-size: 10px; font-weight: 700; letter-spacing: 0.07em;
                 text-transform: uppercase; color: #fff; }

  .lumen-card-title { font-size: 15px; font-weight: 650; color: __INK__;
                      margin: 7px 0 1px; line-height: 1.3; }
  .lumen-code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
                font-size: 11.5px; color: __MUTED__; }
  .lumen-desc { font-size: 12.5px; color: __MUTED__; line-height: 1.55;
                margin: 6px 0 8px; }
  .lumen-meta { font-size: 11.5px; color: __MUTED__; }
  .lumen-meta strong { color: __INK__; font-weight: 600; }
  .lumen-score { display: inline-block; float: right; font-size: 11px;
                 font-weight: 700; color: __NAVY__; }

  .lumen-page-title { font-size: 25px; font-weight: 700; color: __INK__;
                      letter-spacing: -0.02em; margin-bottom: 2px; }
  .lumen-page-sub { font-size: 13px; color: __MUTED__; margin-bottom: 18px; }

  .lumen-detail-title { font-size: 27px; font-weight: 700; color: __INK__;
                        letter-spacing: -0.02em; margin: 10px 0 2px; }

  .lumen-help h3 { font-size: 15px; color: __INK__; margin: 22px 0 6px; }
  .lumen-help p, .lumen-help li { font-size: 13.5px; color: __MUTED__;
                                  line-height: 1.65; }
  .lumen-step { display: inline-block; width: 21px; height: 21px;
                border-radius: 50%; background: __STEP__; color: #fff;
                font-size: 11px; font-weight: 700; text-align: center;
                line-height: 21px; margin-right: 7px; }

  hr { border-color: __BORDER__; }
  [data-testid="stMetricValue"] { font-size: 17px; }
  [data-testid="stMetricLabel"] { font-size: 11.5px; color: __MUTED__; }
</style>
"""
for token, value in [("__INK__", INK), ("__MUTED__", MUTED),
                     ("__BORDER__", BORDER), ("__NAVY__", ACCENT),
                     ("__STEP__", COLOURS["badge_table"])]:
    CSS = CSS.replace(token, value)
st.markdown(CSS, unsafe_allow_html=True)


# --- Data -------------------------------------------------------------------

@st.cache_data
def load_catalog():
    with open(BASE_DIR / "catalog_metadata.json") as f:
        return json.load(f)


@st.cache_data
def load_embeddings():
    path = BASE_DIR / "embeddings.json"
    if not path.exists():
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
    """Embed the search query using Gemini. Returns None if unavailable."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
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
        return result.embeddings[0].values
    except Exception:
        return None


catalog = load_catalog()
embeddings = load_embeddings()
downstream_map = build_downstream(json.dumps(catalog))
has_embeddings = bool(embeddings)


# --- Small render helpers ---------------------------------------------------

def badge(asset_type):
    text, colour = TYPE_STYLE.get(asset_type, ("Unknown", MUTED))
    return f'<span class="lumen-badge" style="background:{colour}">{text}</span>'


def asset_line(name):
    """One upstream/downstream entry: a type badge next to the asset name."""
    asset_type = catalog.get(name, {}).get("type", "")
    return f'{badge(asset_type)} <span class="lumen-code">{name}</span>'


# --- Help section -----------------------------------------------------------

HELP_STEPS = [
    ("Read the sidebar",
     "The counts at the bottom of the sidebar tell you the size of the "
     "catalog: how many assets in total, and how that splits into base "
     "tables and views. A <strong>base table</strong> holds raw data. A "
     "<strong>view</strong> is built from other assets by a SQL query."),
    ("Open an asset",
     "On the Catalog page every asset is a card. Click <strong>View "
     "details</strong> on any card to open it. Use <strong>Back to "
     "catalog</strong> to return. Those are the only two screens."),
    ("Check what an asset depends on",
     "Inside an asset, the <strong>Lineage</strong> tab shows two lists. "
     "Upstream is what this asset reads from. Downstream is what reads "
     "from it. A long downstream list means changing this asset is risky, "
     "because everything on that list is affected."),
    ("Search by keyword",
     "Type into the search box to match text in names, descriptions, "
     "column names and owners. This is literal matching, so the word has "
     "to actually be there."),
    ("Search by meaning",
     "Turn on the <strong>Semantic</strong> switch and the search matches "
     "meaning instead of words. Asking for "
     "<em>which customers spend the most money</em> finds the top "
     "customers view even though it contains neither <em>spend</em> nor "
     "<em>money</em>. Each result shows a match percentage so you can "
     "judge how close it is."),
    ("Switch between light and dark",
     "Open the menu at the <strong>top right</strong> of the page, then "
     "<strong>Settings</strong> and <strong>Appearance</strong>. Pick Light, "
     "Dark, or leave it following your computer's own setting. Both themes "
     "use the same navy and teal palette."),
    ("Narrow the list",
     "The sidebar filters restrict the grid by asset type and by owning "
     "team. They combine with whatever is in the search box. "
     "<strong>Reset filters</strong> clears everything at once."),
]


def render_help():
    st.markdown('<div class="lumen-page-title">How to use Lumen</div>',
                unsafe_allow_html=True)
    st.markdown(
        '<div class="lumen-page-sub">A short guide to finding your way '
        'around the catalog.</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown(
            '<p class="lumen-desc" style="margin:0">Lumen answers three '
            'questions about a data warehouse that are usually hard to '
            'answer: <strong>what data exists</strong>, '
            '<strong>what each table means</strong>, and '
            '<strong>what breaks if you change one</strong>. Everything here '
            'is derived from the warehouse SQL, so the lineage cannot drift '
            'out of date.</p>',
            unsafe_allow_html=True,
        )

    left, right = st.columns(2, gap="large")
    half = (len(HELP_STEPS) + 1) // 2
    for index, (heading, body) in enumerate(HELP_STEPS):
        target = left if index < half else right
        with target:
            st.markdown(
                f'<div class="lumen-help"><h3><span class="lumen-step">'
                f'{index + 1}</span>{heading}</h3><p>{body}</p></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.markdown('<div class="lumen-help"><h3>Worth trying</h3></div>',
                unsafe_allow_html=True)
    examples = [
        ("Semantic search", "which customers spend the most money"),
        ("Semantic search", "who supplies our products"),
        ("Semantic search", "revenue trends over time"),
        ("Keyword search", "revenue"),
    ]
    for mode, query in examples:
        st.markdown(
            f'<p class="lumen-meta" style="margin:3px 0">'
            f'<strong>{mode}</strong> &nbsp; <span class="lumen-code">'
            f'{query}</span></p>',
            unsafe_allow_html=True,
        )

    if not has_embeddings:
        st.divider()
        st.info(
            "Semantic search is switched off because embeddings.json is "
            "missing. Generate it with: python3 embed_catalog.py"
        )


# --- Detail section ---------------------------------------------------------

def render_detail(name):
    info = catalog[name]
    upstream = info.get("source_tables", [])
    downstream = downstream_map.get(name, [])

    if st.button("Back to catalog"):
        st.session_state.selected = None
        st.rerun()

    st.markdown(badge(info["type"]), unsafe_allow_html=True)
    st.markdown(
        f'<div class="lumen-detail-title">'
        f'{info.get("glossary_term", name)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<span class="lumen-code">{name}</span>',
                unsafe_allow_html=True)
    st.markdown(f'<p class="lumen-desc" style="font-size:13.5px">'
                f'{info.get("description", "")}</p>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Owner", info.get("owner", "Unknown"))
    c2.metric("Columns", len(info.get("columns", [])))
    c3.metric("Upstream", len(upstream))
    c4.metric("Downstream", len(downstream))

    st.divider()
    tab_columns, tab_lineage, tab_sql = st.tabs(["Columns", "Lineage", "SQL"])

    with tab_columns:
        column_lineage = info.get("column_lineage", {})
        st.dataframe(
            [
                {
                    "Column": column,
                    "Derived from": ", ".join(column_lineage.get(column, []))
                    or "Not derived, this is a source column",
                }
                for column in info.get("columns", [])
            ],
            hide_index=True,
            width="stretch",
        )

    with tab_lineage:
        col_up, col_down = st.columns(2, gap="large")
        with col_up:
            st.markdown("**Upstream**")
            st.caption("This asset reads from")
            if upstream:
                for source in upstream:
                    st.markdown(asset_line(source), unsafe_allow_html=True)
            else:
                st.info("A raw source table, so nothing feeds it.")
        with col_down:
            st.markdown("**Downstream**")
            st.caption("These read from this asset")
            if downstream:
                for consumer in downstream:
                    st.markdown(asset_line(consumer), unsafe_allow_html=True)
                st.caption(
                    f"Changing this asset affects {len(downstream)} "
                    f"other asset(s)."
                )
            else:
                st.info("Nothing depends on this asset yet.")

    with tab_sql:
        if info.get("sql"):
            sql = info["sql"]
            create_index = sql.upper().find("CREATE VIEW")
            st.code(sql[create_index:] if create_index >= 0 else sql,
                    language="sql")
        else:
            st.info(
                "A raw base table. It is defined in schema.sql and has no "
                "transformation SQL."
            )


# --- Catalog section --------------------------------------------------------

def keyword_matches(name, info, search, type_filter, owner_filter):
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


def semantic_results(query, type_filter, owner_filter):
    """Rank assets by cosine similarity to the query.

    Returns (results, scores, used_fallback). Anything below
    MIN_SIMILARITY is discarded so a nonsense query returns nothing
    rather than a page of confident looking cards.
    """
    query_vec = get_query_embedding(query)
    if query_vec is None:
        results = {
            name: info for name, info in catalog.items()
            if keyword_matches(name, info, query, type_filter, owner_filter)
        }
        return results, {}, True

    scored = []
    for name, vector in embeddings.items():
        info = catalog.get(name)
        if not info:
            continue
        if info["type"] not in type_filter:
            continue
        if info.get("owner") not in owner_filter:
            continue
        score = cosine_similarity(query_vec, vector)
        if score >= MIN_SIMILARITY:
            scored.append((score, name, info))

    scored.sort(reverse=True)
    scored = scored[:MAX_SEMANTIC_RESULTS]
    results = {name: info for _, name, info in scored}
    scores = {name: score for score, name, _ in scored}
    return results, scores, False


def render_card(name, info, score=None):
    with st.container(border=True):
        header = badge(info["type"])
        if score is not None:
            header += (f'<span class="lumen-score">'
                       f'{round(score * 100)}% match</span>')
        st.markdown(header, unsafe_allow_html=True)

        st.markdown(
            f'<div class="lumen-card-title">'
            f'{info.get("glossary_term", name)}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(f'<span class="lumen-code">{name}</span>',
                    unsafe_allow_html=True)

        description = info.get("description", "")
        if len(description) > CARD_DESCRIPTION_LIMIT:
            description = description[:CARD_DESCRIPTION_LIMIT].rstrip() + "..."
        st.markdown(f'<p class="lumen-desc">{description}</p>',
                    unsafe_allow_html=True)

        st.markdown(
            f'<p class="lumen-meta">{info.get("owner", "Unknown")}<br>'
            f'<strong>{len(info.get("columns", []))}</strong> columns'
            f' &nbsp;|&nbsp; '
            f'<strong>{len(info.get("source_tables", []))}</strong> upstream'
            f' &nbsp;|&nbsp; '
            f'<strong>{len(downstream_map.get(name, []))}</strong> downstream'
            f'</p>',
            unsafe_allow_html=True,
        )

        if st.button("View details", key=f"open_{name}", width="stretch"):
            st.session_state.selected = name
            st.rerun()


def render_catalog(search, semantic_on, type_filter, owner_filter):
    used_fallback = False
    scores = {}

    if search and semantic_on and has_embeddings:
        results, scores, used_fallback = semantic_results(
            search, type_filter, owner_filter
        )
        if used_fallback:
            st.warning(
                "GEMINI_API_KEY is not set, so the search fell back to "
                "keyword matching."
            )
            st.caption(f"Showing **{len(results)}** of {len(catalog)} assets")
        else:
            st.caption(
                f"Showing **{len(results)}** asset(s) ranked by meaning "
                f'for "{search}"'
            )
    else:
        results = {
            name: info for name, info in catalog.items()
            if keyword_matches(name, info, search, type_filter, owner_filter)
        }
        st.caption(f"Showing **{len(results)}** of {len(catalog)} assets")

    if not results:
        if search and semantic_on and not used_fallback:
            st.info(
                "Nothing in the catalog is a close enough match. Try "
                "describing the data you want in different words."
            )
        else:
            st.info(
                "No assets match. Clear the search box, or widen the "
                "filters in the sidebar."
            )
        return

    names = list(results)
    columns_per_row = 3
    for row_start in range(0, len(names), columns_per_row):
        row = st.columns(columns_per_row, gap="medium")
        for offset, column in enumerate(row):
            index = row_start + offset
            if index >= len(names):
                break
            name = names[index]
            with column:
                render_card(name, results[name], scores.get(name))


# --- Sidebar and routing ----------------------------------------------------

if "selected" not in st.session_state:
    st.session_state.selected = None

with st.sidebar:
    st.markdown('<div class="lumen-brand">Lumen</div>', unsafe_allow_html=True)
    st.markdown('<div class="lumen-brand-sub">Active Metadata Catalog</div>',
                unsafe_allow_html=True)
    st.divider()

    section = st.radio(
        "Section",
        options=["Catalog", "Help"],
        key="section",
        label_visibility="collapsed",
    )

if section == "Help":
    render_help()
    st.stop()

with st.sidebar:
    st.divider()

    type_filter = st.multiselect(
        "Asset type",
        options=["base_table", "view"],
        default=["base_table", "view"],
        format_func=lambda value: TYPE_STYLE[value][0],
        key="type_filter",
    )

    all_owners = sorted({v["owner"] for v in catalog.values() if v.get("owner")})
    owner_filter = st.multiselect(
        "Owning team", options=all_owners, default=all_owners, key="owner_filter"
    )

    if st.button("Reset filters", width="stretch"):
        for key in ("type_filter", "owner_filter", "search", "semantic_on"):
            st.session_state.pop(key, None)
        st.rerun()

    st.divider()
    total = len(catalog)
    tables = sum(1 for v in catalog.values() if v["type"] == "base_table")
    st.metric("Total assets", total)
    stat_left, stat_right = st.columns(2)
    stat_left.metric("Tables", tables)
    stat_right.metric("Views", total - tables)

    st.divider()
    st.caption(
        "Semantic search ready" if has_embeddings
        else "Semantic search unavailable. Run embed_catalog.py to enable it."
    )
    st.caption(
        "Light and dark themes: use the menu at the top right, "
        "then Settings and Appearance."
    )

if st.session_state.selected:
    render_detail(st.session_state.selected)
    st.stop()

st.markdown('<div class="lumen-page-title">Data Catalog</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="lumen-page-sub">Search the warehouse, read what each asset '
    'means, and trace what depends on it.</div>',
    unsafe_allow_html=True,
)

col_search, col_toggle = st.columns([5, 1], vertical_alignment="center")
with col_search:
    search = st.text_input(
        "Search the catalog",
        placeholder="Search by name, description, column or owner",
        label_visibility="collapsed",
        key="search",
    )
with col_toggle:
    semantic_on = st.toggle(
        "Semantic",
        value=False,
        disabled=not has_embeddings,
        key="semantic_on",
        help=(
            "Match on meaning rather than exact words."
            if has_embeddings
            else "Unavailable. Run embed_catalog.py to generate embeddings."
        ),
    )

render_catalog(search, semantic_on, type_filter, owner_filter)
