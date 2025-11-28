import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

# ------------------- CONFIG -------------------
ADMIN_PASSWORD = "abc123"

CARDS_SHEET_URL = "https://docs.google.com/spreadsheets/d/1_VbZQuf86KRU062VfyLzPU6KP8C3XhZ7MPAvqjfjf0o/export?format=csv&id=1_VbZQuf86KRU062VfyLzPU6KP8C3XhZ7MPAvqjfjf0o&gid=0"
SLABS_SHEET_URL = "https://docs.google.com/spreadsheets/d/16LUG10XJh01vrr_eIkSU3s5votDUZFdB2VSsQZ7ER04/export?format=csv&id=16LUG10XJh01vrr_eIkSU3s5votDUZFdB2VSsQZ7ER04&gid=0"
TRACK_SHEET_URL = "https://docs.google.com/spreadsheets/d/1qe3myLWbS20AqIgEh8DkO9GrnXxWYq2kgeeohsl5hlI/export?format=csv&id=1qe3myLWbS20AqIgEh8DkO9GrnXxWYq2kgeeohsl5hlI&gid=509630493"

# ------------------- PRICE CLEANER -------------------
def clean_price(value):
    if pd.isna(value):
        return 0.0
    value = str(value).replace("$", "").replace(",", "").strip()
    try:
        return float(value)
    except:
        return 0.0

# ------------------- UTIL FUNCTIONS -------------------
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
    }
    df = normalize_columns(df, column_map)
    if "type" not in df.columns:
        df["type"] = "Other"
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
# Priority types with correct capitalization
priority_display = ["Pokemon", "One Piece", "Magic the Gathering"]
priority_lookup = [p.lower() for p in priority_display]

# Extract raw type names
raw_types = [t.strip() for t in cards_df["type"].dropna().unique() if str(t).strip() != ""]

# Match priority types (case-insensitive)
priority_types = []
for disp, key in zip(priority_display, priority_lookup):
    if key in [r.lower() for r in raw_types]:
        priority_types.append(disp)

# Remaining types (A–Z, title-cased for display)
remaining_types = sorted([
    t.title() for t in raw_types
    if t.lower() not in priority_lookup
])

# Final ordered type list
all_types = priority_types + remaining_types

# Build tabs
tabs = st.tabs(all_types + ["Slabs", "Tracking", "Admin Panel"])

# ==========================================================
#                 TYPE TABS (DYNAMIC)
# ==========================================================
for index, t in enumerate(all_types):
    with tabs[index]:
        st.header(f"{t.title()} Cards")

        df = st.session_state.cards_df
        type_df = df[df["type"].str.lower() == t.lower()].dropna(subset=["image_link", "name"])
        type_df["market_price_clean"] = type_df["market_price"].apply(clean_price)

        # ------------------- FILTERS -------------------
        st.subheader("Filters")
        col1, col2, col3, col4 = st.columns([1,1,1,1])

        # SET Filter
        with col1:
            sets_available = sorted(type_df["set"].dropna().unique())
            selected_set = st.selectbox("Set", ["All"] + sets_available, key=f"set_{t}")

        # SEARCH BAR
        with col2:
            search_query = st.text_input("Search Name", "", key=f"search_{t}")

        # SORTING
        with col3:
            sort_option = st.selectbox(
                "Sort By",
                ["Name (A-Z)", "Name (Z-A)", "Price Low→High", "Price High→Low"],
                key=f"sort_{t}"
            )

        # GRID SIZE
        with col4:
            grid_size = st.selectbox("Grid", [3,4], key=f"grid_{t}")

        # ------------------- PRICE SLIDER -------------------
        st.subheader("Price Filter")
        min_possible = float(type_df["market_price_clean"].min())
        max_possible = float(type_df["market_price_clean"].max())
        if min_possible == max_possible:
            st.info(f"All cards have the same price: ${min_possible:.2f}")
            min_price, max_price = min_possible, max_possible
        else:
            min_price, max_price = st.slider(
                "Market Price Range",
                min_value=min_possible,
                max_value=max_possible,
                value=(min_possible, max_possible),
                key=f"price_{t}"
            )

        # ------------------- APPLY FILTERS -------------------
        if selected_set != "All":
            type_df = type_df[type_df["set"] == selected_set]
        if search_query.strip():
            type_df = type_df[type_df["name"].str.contains(search_query, case=False, na=False)]
        type_df = type_df[(type_df["market_price_clean"] >= min_price) & (type_df["market_price_clean"] <= max_price)]
        if selected_set == "All":
            type_df = type_df.sort_values("set", ascending=False)

        if sort_option == "Name (A-Z)":
            type_df = type_df.sort_values("name")
        elif sort_option == "Name (Z-A)":
            type_df = type_df.sort_values("name", ascending=False)
        elif sort_option == "Price Low→High":
            type_df = type_df.sort_values("market_price_clean")
        elif sort_option == "Price High→Low":
            type_df = type_df.sort_values("market_price_clean", ascending=False)

        # ------------------- PAGINATION -------------------
        st.subheader("Results")
        per_page = st.selectbox("Results per page", [9,45,99], index=0, key=f"per_page_{t}")
        if f"page_{t}" not in st.session_state:
            st.session_state[f"page_{t}"] = 1

        total_items = len(type_df)
        total_pages = (total_items - 1) // per_page + 1
        start_idx = (st.session_state[f"page_{t}"] - 1) * per_page
        end_idx = start_idx + per_page
        page_df = type_df.iloc[start_idx:end_idx]

        for i in range(0, len(page_df), grid_size):
            cols = st.columns(grid_size)
            for j, card in enumerate(page_df.iloc[i:i + grid_size].to_dict(orient="records")):
                with cols[j]:
                    st.image(card["image_link"], use_container_width=True)
                    st.markdown(f"**{card['name']}**")
                    st.markdown(
                        f"Set: {card['set']}  \n"
                        f"Condition: {card['condition']}  \n"
                        f"Sell: {card['sell_price']} | Market: {card['market_price']}"
                    )

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

# ------------------- SINGLE GLOBAL REFRESH BUTTON -------------------
st.markdown("---")
with st.container():
    cols = st.columns([2,2,1])
    with cols[1]:
        if st.button("🔄 Refresh All", help="Reload Cards + Slabs + Tracking", key="refresh_all_global"):
            st.session_state.cards_df = load_cards()
            st.session_state.slabs_df = load_slabs()
            st.session_state.track_df = load_tracking_sheet()
            st.success("All data refreshed!")

# ==========================================================
#                          SLABS
# ==========================================================
with tabs[len(all_types)]:
    st.header("Slabs")
    if st.button("Refresh Slabs", key="refresh_slabs"):
        st.session_state.slabs_df = load_slabs()
        st.success("Slabs refreshed!")

    df = st.session_state.slabs_df.dropna(subset=["image_link","name"])
    for i in range(0, len(df), 3):
        cols = st.columns(3)
        for j, slab in enumerate(df.iloc[i:i+3].to_dict(orient="records")):
            with cols[j]:
                st.image(slab["image_link"], use_container_width=True)
                st.markdown(f"**{slab['name']}**")
                st.markdown(
                    f"Set: {slab['set']}  \n"
                    f"PSA Grade: {slab['psa_grade']}  \n"
                    f"Sell: {slab['sell_price']} | Market: {slab['market_price']}"
                )

# ==========================================================
#                       TRACKING TAB
# ==========================================================
with tabs[len(all_types)+1]:
    st.header("Card & Slab Values Over Time")

    df = st.session_state.track_df

    # Filters
    st.subheader("Filters")
    types_available = sorted(df["type"].unique())
    selected_types = st.multiselect("Select Types", types_available, default=types_available)

    if selected_types:
        df = df[df["type"].isin(selected_types)]

    # Line Graph: card_value
    st.subheader("Card Value Over Time")
    fig_card = px.line(
        df,
        x="time",
        y="card_value",
        color="type",
        markers=True,
        title="Card Value Tracking by Type"
    )
    st.plotly_chart(fig_card, use_container_width=True)

    # Line Graph: slab_value
    st.subheader("Slab Value Over Time")
    fig_slab = px.line(
        df,
        x="time",
        y="slab_value",
        color="type",
        markers=True,
        title="Slab Value Tracking by Type"
    )
    st.plotly_chart(fig_slab, use_container_width=True)

# ==========================================================
#                     ADMIN PANEL
# ==========================================================
with tabs[len(all_types)+2]:
    st.header("Admin Panel - PSA Cert Fetcher")

    # Admin password
    password = st.text_input("Enter Admin Password", type="password")
    if password == ADMIN_PASSWORD:
        st.success("Access granted!")
        st.subheader("Existing Cards (Table View)")
        st.dataframe(st.session_state.cards_df)
        
        
        # PSA API token (replace with your real token)
        API_TOKEN = "tKlFIkdgLf4iFEtfpVWVwY7mZLl6CvAkjmazQ6NGFU2htqOefrgLr64e7GmHs23SHN8a_Y3_URO4tbzSe12vIjqf2WDm-qST759n46r9GG0-KKeKNfVs6yQC03H3WAvzf-8LsIp8tkXw910cyzQWDh4yNJ-PdtTmSaSwda_iP6x9P4eRKTaSRQsnH-Sx7tSH7WAKGLiS16vZtObHDKg0gm2o_SYYbkmYed8ZBELNHrBV3T10rQ1tLJEqXfFfbMGJY38daNSMlGdgE-phLWr1PVM_FQqWaBcentfOR8Ltvvw0csIy"
        
        st.title("PSA Card Cert Number Checker")
        
        # Step 1: Upload Excel file
        uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            
            if 'cert_number' not in df.columns:
                st.error("Excel file must have a 'cert_number' column")
            else:
                cert_numbers = df['cert_number'].dropna().unique()
                st.write(f"Found {len(cert_numbers)} cert numbers")
                
                # Step 2 & 3: Query PSA API
                results = []
                for cert in cert_numbers:
                    url = f"https://api.psacard.com/publicapi/cert/GetByCertNumber/{cert}"
                    headers = {
                        "Authorization": f"Bearer {API_TOKEN}",
                        "Content-Type": "application/json"
                    }
                    response = requests.get(url, headers=headers)
                    if response.status_code == 200:
                        data = response.json()
                        st.write(f"Cert Number: {cert}")
                        st.json(data)  # Display each response
                        
                        # Step 4: Populate new columns in the dataframe
                        # Adjust keys based on PSA API response structure
                        df.loc[df['cert_number'] == cert, 'grade'] = data.get('grade')
                        df.loc[df['cert_number'] == cert, 'serial_number'] = data.get('serialNumber')
                        df.loc[df['cert_number'] == cert, 'card_name'] = data.get('cardName')
                    else:
                        st.warning(f"Failed to fetch data for cert {cert}: {response.status_code}")
                
                # Step 5: Preview updated table
                st.subheader("Preview Updated Table")
                st.dataframe(df)
                
                # Step 6: Export as Excel
                towrite = io.BytesIO()
                df.to_excel(towrite, index=False, engine='openpyxl')
                towrite.seek(0)
                st.download_button(
                    label="Download updated Excel",
                    data=towrite,
                    file_name="updated_cert_data.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )



