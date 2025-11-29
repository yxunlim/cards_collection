import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import subprocess
import re
import io

# ------------------- CONFIG -------------------
ADMIN_PASSWORD = "abc123"

CARDS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_VbZQuf86KRU062VfyLzPU6KP8C3XhZ7MPAvqjfjf0o/export?format=csv&id=1_VbZQuf86KRU062VfyLzPU6KP8C3XhZ7MPAvqjfjf0o&gid=0"
SLABS_SHEET_URL = "https://docs.google.com/spreadsheets/d/16LUG10XJh01vrr_eIkSU3s5votDUZFdB2VSsQZ7ER04/export?format=csv"
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

def make_safe_key(name):
    """Sanitize string to use as Streamlit widget key"""
    return re.sub(r"[^a-z0-9_]+", "_", name.lower())

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
        df["quantity"] = 0
    if "market_price" not in df.columns:
        df["market_price"] = 0.0
    return df

@st.cache_data
def load_slabs():
    response = requests.get(SLABS_SHEET_URL)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text))

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()

    # Map columns
    column_map = {
        "certnumber": "item_no",
        "cardgrade": "psa_grade",
        "sell_price": "sell_price",
        "image_link": "image_link"
    }
    df = normalize_columns(df, column_map)

    # Build display 'name' column safely
    df['name'] = df.apply(
        lambda row: f"{row.get('subject', '')} #{row.get('cardnumber', '')}" +
                    (f" {row.get('variety')}" if pd.notna(row.get('variety')) else ""),
        axis=1
    )

    # Ensure required columns exist
    for col in ["item_no", "name", "set", "psa_grade", "sell_price", "image_link"]:
        if col not in df.columns:
            df[col] = ""

    return df

@st.cache_data
def load_tracking_sheet():
    df = pd.read_csv(TRACK_SHEET_URL)
    df.columns = df.columns.str.strip().str.lower()
    df["time"] = pd.to_datetime(df.get("time", pd.Series()), errors="coerce", dayfirst=True)
    df["card_value"] = pd.to_numeric(df.get("card_value", 0), errors="coerce").fillna(0)
    df["slab_value"] = pd.to_numeric(df.get("slab_value", 0), errors="coerce").fillna(0)
    df["type"] = df.get("type", "").astype(str).str.strip()
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

priority_types = [disp for disp, key in zip(priority_display, priority_lookup) if key in [r.lower() for r in raw_types]]
remaining_types = sorted([t.title() for t in raw_types if t.lower() not in priority_lookup])
all_types = priority_types + remaining_types

tabs = st.tabs(all_types + ["Slabs", "Tracking", "Admin Panel"])

# =================== TYPE TABS ===================
for index, t in enumerate(all_types):
    with tabs[index]:
        st.header(f"{t.title()} Cards")

        df = st.session_state.cards_df
        type_df = df[df["type"].str.lower() == t.lower()].dropna(subset=["name"])

        type_df = type_df[type_df["quantity"].astype(str).fillna("0").replace("", "0").astype(int) > 0]
        type_df["market_price_clean"] = type_df["market_price"].apply(clean_price)

        # Filters
        st.subheader("Filters")
        col1, col2, col3 = st.columns([1,1,1])
        safe_t = make_safe_key(t)
        tab_idx = index

        with col1:
            sets_available = sorted(type_df["set"].dropna().unique())
            selected_set = st.selectbox(
                "Set", ["All"] + sets_available, 
                key=f"set_{safe_t}_{tab_idx}"
            )
        with col2:
            search_query = st.text_input(
                "Search Name", "", 
                key=f"search_{safe_t}_{tab_idx}"
            )
        with col3:
            sort_option = st.selectbox(
                "Sort By",
                ["Name (A-Z)", "Name (Z-A)", "Price Low→High", "Price High→Low"],
                key=f"sort_{safe_t}_{tab_idx}"
            )

        # Price slider
        st.subheader("Price Filter")
        min_possible = float(type_df["market_price_clean"].min())
        max_possible = float(type_df["market_price_clean"].max())
        if min_possible == max_possible:
            min_price, max_price = min_possible, max_possible
        else:
            min_price, max_price = st.slider(
                "Market Price Range",
                min_value=min_possible,
                max_value=max_possible,
                value=(min_possible, max_possible),
                key=f"price_{safe_t}_{tab_idx}"
            )

        # Apply filters
        if selected_set != "All":
            type_df = type_df[type_df["set"] == selected_set]
        if search_query.strip():
            type_df = type_df[type_df["name"].str.contains(search_query, case=False, na=False)]
        type_df = type_df[(type_df["market_price_clean"] >= min_price) & (type_df["market_price_clean"] <= max_price)]
        if selected_set == "All":
            type_df = type_df.sort_values("set", ascending=False)

        # Sorting
        if sort_option == "Name (A-Z)":
            type_df = type_df.sort_values("name")
        elif sort_option == "Name (Z-A)":
            type_df = type_df.sort_values("name", ascending=False)
        elif sort_option == "Price Low→High":
            type_df = type_df.sort_values("market_price_clean")
        elif sort_option == "Price High→Low":
            type_df = type_df.sort_values("market_price_clean", ascending=False)

        # Pagination
        st.subheader("Results")
        per_page = st.selectbox("Results per page", [9,45,99], index=0, key=f"per_page_{safe_t}_{tab_idx}")
        if f"page_{safe_t}_{tab_idx}" not in st.session_state:
            st.session_state[f"page_{safe_t}_{tab_idx}"] = 1

        total_items = len(type_df)
        total_pages = (total_items - 1) // per_page + 1
        start_idx = (st.session_state[f"page_{safe_t}_{tab_idx}"] - 1) * per_page
        end_idx = start_idx + per_page
        page_df = type_df.iloc[start_idx:end_idx]

        grid_size = 3
        for i in range(0, len(page_df), grid_size):
            cols = st.columns(grid_size)
            for j, card in enumerate(page_df.iloc[i:i + grid_size].to_dict(orient="records")):
                with cols[j]:
                    img_link = card.get("image_link", "")
                    if img_link and img_link.lower() != "loading...":
                        st.image(img_link, use_container_width=True)
                    else:
                        st.image("https://via.placeholder.com/150", use_container_width=True)
                    st.markdown(f"**{card['name']}**")
                    st.markdown(
                        f"Set: {card.get('set','')}  \n"
                        f"Condition: {card.get('condition','')}  \n"
                        f"Quantity: {card.get('quantity','')}  \n"
                        f"Sell: {card.get('sell_price','')} | Market: {card.get('market_price','')}"
                    )

        # Pagination buttons
        col_prev, col_spacer, col_page_info, col_next = st.columns([1,1,2,1])
        with col_prev:
            if st.button("⬅️ Previous", key=f"prev_{safe_t}_{tab_idx}") and st.session_state[f"page_{safe_t}_{tab_idx}"] > 1:
                st.session_state[f"page_{safe_t}_{tab_idx}"] -= 1
        with col_page_info:
            st.markdown(f"Page {st.session_state[f'page_{safe_t}_{tab_idx}']} of {total_pages}")
        with col_next:
            if st.button("➡️ Next", key=f"next_{safe_t}_{tab_idx}") and st.session_state[f"page_{safe_t}_{tab_idx}"] < total_pages:
                st.session_state[f"page_{safe_t}_{tab_idx}"] += 1

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
                if img_link and img_link.lower() != "loading...":
                    st.image(img_link, use_container_width=True)
                else:
                    st.image("https://via.placeholder.com/150", use_container_width=True)
                st.markdown(f"**{slab['name']}**")
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
            
    st.subheader("Check PSA Certificate")
    
    cert_number = st.text_input("Certificate Number:", type="password", placeholder="Enter your certificate number")
    
    if st.button("Send"):
        if not cert_number.strip():
            st.warning("Please enter a certificate number")
        else:
            try:
                curl_command = f'''curl -X GET "https://api.psacard.com/publicapi/cert/GetByCertNumber/{cert_number}" \
    -H "Content-Type: application/json" \
    -H "Authorization: bearer 7zU2hjuSA-4oYqA5uaPX7oUq5SwKIDh8D4RHs4FpVpFJhVTND7TTaoy8K2JZAg6yBbVyumJHiCo-TUMWN3cDmW_cnFyEtjXBUpoWR_ptiFI6PvU6fH1AKwnTsvniUSJHt_t6QjbcfCIEjhcugHnn8dxFwsAoOUnozd7etyqtEjNOw9xDuVeLpIHN-lAVvxb7d1I1GNVNx2XHARx2XKhLEqlC8OOJDcCYif-u-eSEcdIBPEQW7jrCSBXmYjFJZ6nRO8Ha0IBpixxZ-7uAUyXtBNsPAnatTaBT9E6jzgqNAeNY56pW"'''
                result = subprocess.run(curl_command, shell=True, capture_output=True, text=True)
                st.subheader("Output")
                if result.stdout:
                    st.code(result.stdout)
                if result.stderr:
                    st.subheader("Errors")
                    st.code(result.stderr)
            except Exception as e:
                st.error(f"An error occurred: {e}")
