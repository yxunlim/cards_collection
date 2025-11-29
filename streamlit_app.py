import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import subprocess

# ------------------- GLOBAL UI (MOBILE + DESKTOP) -------------------
st.markdown("""
<style>
/* ----------------------------
   GLOBAL LAYOUT IMPROVEMENTS
-----------------------------*/
.block-container {
    padding-top: 1.5rem;
}

/* Improve card text readability */
.card-text, .stMarkdown {
    word-wrap: break-word !important;
    white-space: normal !important;
    line-height: 1.25rem;
}

/* Global image behavior */
img {
    width: 100% !important;
    height: auto !important;
    border-radius: 10px;
    display: block;
}

/* Reduce excessive spacing between elements */
.css-1kyxreq, .css-12oz5g7 {  
    margin-bottom: 0.5rem !important;
}

/* ----------------------------
   MOBILE OPTIMIZATIONS
-----------------------------*/
@media (max-width: 600px) {

    /* Reduce side padding */
    .block-container {
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* Slightly smaller text */
    .stMarkdown, .card-text {
        font-size: 0.85rem !important;
    }

    /* Make buttons easy to tap (pagination / refresh) */
    .stButton > button {
        width: 100% !important;
        padding: 12px !important;
        font-size: 1rem !important;
    }

    /* Shrink image top margin */
    img {
        margin-top: 0.2rem !important;
    }
}

/* ----------------------------
   DESKTOP OPTIMIZATIONS
-----------------------------*/
@media (min-width: 1000px) {
    .stMarkdown, .card-text {
        font-size: 1rem;
    }
}
</style>
""", unsafe_allow_html=True)

# ------------------- CONFIG -------------------
ADMIN_PASSWORD = "abc123"

CARDS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_VbZQuf86KRU062VfyLzPU6KP8C3XhZ7MPAvqjfjf0o/export?format=csv&id=1_VbZQuf86KRU062VfyLzPU6KP8C3XhZ7MPAvqjfjf0o&gid=0"
SLABS_SHEET_URL = "https://docs.google.com/spreadsheets/d/16LUG10XJh01vrr_eIkSU3s5votDUZFdB2VSsQZ7ER04/export?format=csv&id=16LUG10XJh01vrr_eIkSU3s5votDUZFdB2VSsQZ7ER04&gid=0"
TRACK_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qe3myLWbS20AqIgEh8DkO9GrnXxWYq2kgeeohsl5hlI/export?format=csv&id=1qe3myLWbS20AqIgEh8DkO9GrnXxWYq2kgeeohsl5hlI&gid=509630493"

# ------------------- UTIL FUNCTIONS -------------------
def clean_price(value):
    if pd.isna(value):
        return 0.0
    value = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(value)
    except:
        return 0.0

def normalize_columns(df, column_map):
    df.columns = df.columns.str.strip().str.lower()
    df = df.rename(columns={k.lower(): v for k, v in column_map.items() if k.lower() in df.columns})
    return df

# ------------------- LOAD DATA -------------------
@st.cache_data
def load_cards():
    df = pd.read_csv(CARDS_SHEET_URL)
    column_map = {
        "item no": "item_no",
        "name": "name",
        "set": "set",
        "type": "type",
        "category": "type",
        "card type": "type",
        "game": "type",
        "condition": "condition",
        "sell price": "sell_price",
        "image link": "image_link",
        "market price": "market_price",
        "quantity": "quantity"
    }
    df = normalize_columns(df, column_map)

    if "type" not in df.columns:
        df["type"] = "Other"

    if "quantity" not in df.columns:
        df["quantity"] = ""

    return df

@st.cache_data
def load_slabs():
    df = pd.read_csv(SLABS_SHEET_URL)
    column_map = {
        "item no": "item_no",
        "name": "name",
        "set": "set",
        "psa grade": "psa_grade",
        "sell price": "sell_price",
        "image link": "image_link",
        "market price": "market_price"
    }
    df = normalize_columns(df, column_map)
    return df

@st.cache_data
def load_tracking_sheet():
    df = pd.read_csv(TRACK_SHEET_URL)
    df.columns = df.columns.str.strip().str.lower()
    df["time"] = pd.to_datetime(df["time"], dayfirst=True)
    df["card_value"] = pd.to_numeric(df["card_value"], errors="coerce").fillna(0)
    df["slab_value"] = pd.to_numeric(df["slab_value"], errors="coerce").fillna(0)
    df["type"] = df["type"].str.strip()
    return df

# ------------------- SESSION STATE -------------------
if "cards_df" not in st.session_state:
    st.session_state.cards_df = load_cards()
if "slabs_df" not in st.session_state:
    st.session_state.slabs_df = load_slabs()
if "track_df" not in st.session_state:
    st.session_state.track_df = load_tracking_sheet()

# ------------------- BUILD TABS -------------------
cards_df = st.session_state.cards_df

priority_display = ["Pokemon", "One Piece", "Magic the Gathering"]
priority_lookup = [p.lower() for p in priority_display]

raw_types = [t.strip() for t in cards_df["type"].dropna().unique() if str(t).strip() != ""]

priority_types = []
for disp, key in zip(priority_display, priority_lookup):
    if key in [r.lower() for r in raw_types]:
        priority_types.append(disp)

remaining_types = sorted([
    t.title() for t in raw_types
    if t.lower() not in priority_lookup
])

all_types = priority_types + remaining_types

tabs = st.tabs(all_types + ["Slabs", "Tracking", "Admin Panel"])

# =================== TYPE TABS ===================
for index, t in enumerate(all_types):
    with tabs[index]:
        st.header(f"{t.title()} Cards")

        df = st.session_state.cards_df
        type_df = df[df["type"].str.lower() == t.lower()].dropna(subset=["name"])

        # Skip items with quantity = 0
        if "quantity" in type_df.columns:
            # convert safely to int; blanks -> 0
            try:
                type_df["quantity_norm"] = type_df["quantity"].astype(str).fillna("").replace("", "0").astype(int)
                type_df = type_df[type_df["quantity_norm"] > 0].drop(columns=["quantity_norm"])
            except Exception:
                # if conversion fails, keep rows where quantity is truthy string
                type_df = type_df[type_df["quantity"].astype(str).str.strip() != "0"].copy()

        # If no items after filtering, show message and skip rendering heavy UI
        if type_df.empty:
            st.info("No items to display for this type.")
            continue

        # Clean price
        type_df["market_price_clean"] = type_df["market_price"].apply(clean_price)

        # Filters
        st.subheader("Filters")
        col1, col2, col3, col4 = st.columns([1,1,1,1])
        with col1:
            sets_available = sorted(type_df["set"].dropna().unique())
            selected_set = st.selectbox("Set", ["All"] + sets_available, key=f"set_{t}")
        with col2:
            search_query = st.text_input("Search Name", "", key=f"search_{t}")
        with col3:
            sort_option = st.selectbox(
                "Sort By",
                ["Name (A-Z)", "Name (Z-A)", "Price Low→High", "Price High→Low"],
                key=f"sort_{t}"
            )
        with col4:
            grid_size = 3  # FIXED GRID SIZE

        # Price slider
        st.subheader("Price Filter")
        # guard against weird min/max
        min_possible = type_df["market_price_clean"].min()
        max_possible = type_df["market_price_clean"].max()
        # if NaN, treat as 0
        if pd.isna(min_possible):
            min_possible = 0.0
        if pd.isna(max_possible):
            max_possible = 0.0
        min_possible = float(min_possible)
        max_possible = float(max_possible)

        if min_possible == max_possible:
            min_price, max_price = min_possible, max_possible
        else:
            min_price, max_price = st.slider(
                "Market Price Range",
                min_value=min_possible,
                max_value=max_possible,
                value=(min_possible, max_possible),
                key=f"price_{t}"
            )

        # Apply filters
        filtered_df = type_df.copy()
        if selected_set != "All":
            filtered_df = filtered_df[filtered_df["set"] == selected_set]
        if search_query.strip():
            filtered_df = filtered_df[filtered_df["name"].str.contains(search_query, case=False, na=False)]
        filtered_df = filtered_df[(filtered_df["market_price_clean"] >= min_price) & (filtered_df["market_price_clean"] <= max_price)]
        if selected_set == "All":
            filtered_df = filtered_df.sort_values("set", ascending=False)

        if sort_option == "Name (A-Z)":
            filtered_df = filtered_df.sort_values("name")
        elif sort_option == "Name (Z-A)":
            filtered_df = filtered_df.sort_values("name", ascending=False)
        elif sort_option == "Price Low→High":
            filtered_df = filtered_df.sort_values("market_price_clean")
        elif sort_option == "Price High→Low":
            filtered_df = filtered_df.sort_values("market_price_clean", ascending=False)

        # Pagination
        st.subheader("Results")
        per_page = st.selectbox("Results per page", [9,45,99], index=0, key=f"per_page_{t}")
        if f"page_{t}" not in st.session_state:
            st.session_state[f"page_{t}"] = 1

        total_items = len(filtered_df)
        total_pages = (total_items - 1) // per_page + 1 if total_items > 0 else 1
        start_idx = (st.session_state[f"page_{t}"] - 1) * per_page
        end_idx = start_idx + per_page
        page_df = filtered_df.iloc[start_idx:end_idx]

        # Render cards in fixed 3-column grid
        for i in range(0, len(page_df), grid_size):
            row_cards = page_df.iloc[i:i + grid_size].to_dict(orient="records")
            cols = st.columns(grid_size)
            for j, card in enumerate(row_cards):
                with cols[j]:
                    img_link = card.get("image_link", "")
                    if img_link and str(img_link).strip().lower() != "loading...":
                        st.image(img_link, use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/150", use_container_width=True)

                    # Title (always shown)
                    st.markdown(f"**{card.get('name','')}**")

                    # Responsive card details block (no Quantity line if blank/0)
                    quantity_val = card.get("quantity", "")
                    quantity_display = ""
                    try:
                        if str(quantity_val).strip() != "" and int(str(quantity_val).strip()) != 0:
                            quantity_display = f"Quantity: {quantity_val}<br>"
                    except Exception:
                        if str(quantity_val).strip() != "" and str(quantity_val).strip() != "0":
                            quantity_display = f"Quantity: {quantity_val}<br>"

                    st.markdown(f"""
                    <div class="card-text">
                    Set: {card.get('set','')}<br>
                    Condition: {card.get('condition','')}<br>
                    {quantity_display}
                    Sell: {card.get('sell_price','')} | Market: {card.get('market_price','')}
                    </div>
                    """, unsafe_allow_html=True)

        # Pagination buttons
        col_prev, col_page, col_next = st.columns([1,2,1])
        with col_prev:
            if st.button("⬅️ Previous", key=f"prev_{t}") and st.session_state[f"page_{t}"] > 1:
                st.session_state[f"page_{t}"] -= 1
        with col_page:
            st.markdown(f"Page {st.session_state[f'page_{t}']} of {total_pages}")
        with col_next:
            if st.button("➡️ Next", key=f"next_{t}") and st.session_state[f"page_{t}"] < total_pages:
                st.session_state[f"page_{t}"] += 1

# ------------------- GLOBAL REFRESH -------------------
st.markdown("---")
with st.container():
    cols = st.columns([2,2,1])
    with cols[1]:
        if st.button("🔄 Refresh All", key="refresh_all_global"):
            st.session_state.cards_df = load_cards()
            st.session_state.slabs_df = load_slabs()
            st.session_state.track_df = load_tracking_sheet()
            st.success("All data refreshed!")

# =================== SLABS TAB ===================
with tabs[len(all_types)]:
    st.header("Slabs")
    if st.button("Refresh Slabs", key="refresh_slabs"):
        st.session_state.slabs_df = load_slabs()
        st.success("Slabs refreshed!")

    df = st.session_state.slabs_df.dropna(subset=["name"])
    for i in range(0, len(df), 3):
        cols = st.columns(3)
        for j, slab in enumerate(df.iloc[i:i+3].to_dict(orient="records")):
            with cols[j]:
                img_link = slab.get("image_link", "")
                if img_link and str(img_link).strip().lower() != "loading...":
                    st.image(img_link, use_container_width=True)
                else:
                    st.image("https://via.placeholder.com/150", use_container_width=True)
                st.markdown(f"**{slab.get('name','')}**")
                st.markdown(
                    f"Set: {slab.get('set','')}  \n"
                    f"PSA Grade: {slab.get('psa_grade','')}  \n"
                    f"Sell: {slab.get('sell_price','')} | Market: {slab.get('market_price','')}"
                )

# =================== TRACKING TAB ===================
with tabs[len(all_types)+1]:
    st.header("Card & Slab Values Over Time")
    df = st.session_state.track_df

    st.subheader("Filters")
    types_available = sorted(df["type"].unique())
    selected_types = st.multiselect("Select Types", types_available, default=types_available)

    if selected_types:
        df = df[df["type"].isin(selected_types)]

    st.subheader("Card Value Over Time")
    fig_card = px.line(df, x="time", y="card_value", color="type", markers=True, title="Card Value Tracking")
    st.plotly_chart(fig_card, use_container_width=True)

    st.subheader("Slab Value Over Time")
    fig_slab = px.line(df, x="time", y="slab_value", color="type", markers=True, title="Slab Value Tracking")
    st.plotly_chart(fig_slab, use_container_width=True)

# =================== ADMIN PANEL ===================
with tabs[len(all_types)+2]:
    st.header("Admin Panel - PSA Cert Fetcher")

    password = st.text_input("Enter Admin Password", type="password")
    if password == ADMIN_PASSWORD:
        st.success("Access granted!")
        st.subheader("Existing Cards (Table View)")
        st.dataframe(st.session_state.cards_df)

        # Mini Terminal for cURL Requests
        st.subheader("Mini Terminal for cURL Requests")
        curl_command = st.text_area("Enter cURL command:", placeholder="e.g., curl https://api.github.com")
        if st.button("Run CURL"):
            if curl_command.strip() == "":
                st.warning("Please enter a cURL command")
            else:
                try:
                    result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
                    st.subheader("Output")
                    if result.stdout:
                        st.code(result.stdout)
                    if result.stderr:
                        st.subheader("Errors")
                        st.code(result.stderr)
                except Exception as e:
                    st.error(f"An error occurred: {e}")
