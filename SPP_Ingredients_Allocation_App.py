import pandas as pd
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from dotenv import load_dotenv
import os

load_dotenv()

# Cache function for Google Sheets connection
@st.cache_data
def load_data_from_google_sheet():
    scope = ["https://spreadsheets.google.com/feeds", 
             'https://www.googleapis.com/auth/spreadsheets',
             "https://www.googleapis.com/auth/drive.file", 
             "https://www.googleapis.com/auth/drive"]
    
    credentials = {
        "type": "service_account",
        "project_id": os.getenv("GOOGLE_PROJECT_ID"),
        "private_key_id": os.getenv("GOOGLE_PRIVATE_KEY_ID"),
        "private_key": os.getenv("GOOGLE_PRIVATE_KEY").replace("\\n", "\n"),
        "client_email": os.getenv("GOOGLE_CLIENT_EMAIL"),
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
        "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
        "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
        "client_x509_cert_url": os.getenv("GOOGLE_CLIENT_X509_CERT_URL")
    }

    client_credentials = ServiceAccountCredentials.from_json_keyfile_dict(credentials, scope)
    client = gspread.authorize(client_credentials)
    worksheet = client.open("BROWNS STOCK MANAGEMENT").worksheet("CHECK_OUT")
    
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    df.columns = ["DATE", "ITEM_SERIAL", "ITEM NAME", "ISSUED_TO", "QUANTITY", 
                  "UNIT_OF_MEASURE", "ITEM_CATEGORY", "WEEK", "REFERENCE", 
                  "DEPARTMENT_CAT", "BATCH NO.", "STORE", "RECEIVED BY"]
    
    df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    df["QUANTITY"] = pd.to_numeric(df["QUANTITY"], errors="coerce")
    df.dropna(subset=["QUANTITY"], inplace=True)
    df["QUARTER"] = df["DATE"].dt.to_period("Q")
    
    return df[df["DATE"].dt.year >= 2024]

# Cache proportion calculations to improve performance
@st.cache_data
def calculate_proportion(df, identifier):
    identifier = str(identifier).lower()
    filtered_df = df[(df["ITEM_SERIAL"].astype(str).str.lower() == identifier) |
                     (df["ITEM NAME"].str.lower() == identifier)]

    if filtered_df.empty:
        return None

    usage_summary = filtered_df.groupby("DEPARTMENT_CAT")["QUANTITY"].sum()
    proportions = (usage_summary / usage_summary.sum()) * 100
    proportions.sort_values(ascending=False, inplace=True)

    return proportions.reset_index()

def allocate_quantity(df, item_quantities):
    allocations = {}
    for item, quantity in item_quantities.items():
        proportions = calculate_proportion(df, item)
        if proportions is None:
            continue

        proportions["Allocated Quantity"] = (proportions["QUANTITY"] / 100) * quantity
        proportions["Allocated Quantity"] = proportions["Allocated Quantity"].round(0)

        # Rename columns for better readability
        proportions.rename(columns={"DEPARTMENT_CAT": "Department", "QUANTITY": "Proportion (%)"}, inplace=True)
        
        allocations[item] = proportions

    return allocations

# Streamlit UI
st.markdown("""
    <style>
        .title {
            text-align: center;
            font-size: 42px;
            font-weight: bold;
            color: #FFC300;
            font-family: 'Arial', sans-serif;
        }
        .subtext {
            text-align: center;
            font-size: 18px;
            color: #555;
        }
        .footer {
            text-align: center;
            font-size: 14px;
            margin-top: 20px;
            color: #888;
        }
        .stNumberInput > div {
            margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='title'>SPP Ingredients Allocation App</h1>", unsafe_allow_html=True)
st.markdown("<p class='subtext'>Optimize ingredient allocation based on historical data</p>", unsafe_allow_html=True)

data = load_data_from_google_sheet()
unique_item_names = data["ITEM NAME"].unique().tolist()

selected_identifiers = st.multiselect("🔹 Select Item Serial(s) or Name(s):", unique_item_names, max_selections=10)

item_quantities = {}
if selected_identifiers:
    st.subheader("📌 Enter Available Quantities")
    cols = st.columns(len(selected_identifiers))
    for i, item in enumerate(selected_identifiers):
        with cols[i]:
            item_quantities[item] = st.number_input(f"{item}:", min_value=0.0, step=0.1, key=item)

if st.button("🚀 Calculate Allocation"):
    if selected_identifiers and any(q > 0 for q in item_quantities.values()):
        result = allocate_quantity(data, item_quantities)
        if result:
            st.markdown("<h3 style='text-align: center;'>📊 Allocation Results</h3>", unsafe_allow_html=True)
            for item, table in result.items():
                st.subheader(f"🔹 Allocation for {item}:")
                st.dataframe(table.style.set_properties(**{'text-align': 'center'}), use_container_width=True)
        else:
            st.error("❌ No matching data found for the selected items!")
    else:
        st.warning("⚠️ Please select valid item(s) and enter a quantity.")

st.markdown("<p class='footer'>Developed by Brown's Data Team, ©2025</p>", unsafe_allow_html=True)