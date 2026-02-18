import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION & SETTINGS ---
st.set_page_config(page_title="Petersen Family Budget", page_icon="💰", layout="centered")

# CSS for Mobile Optimization (Samsung S25 / Tablet)
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #007bff; color: white; }
    .stTextInput>div>div>input { border-radius: 10px; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS CONNECTION ---
# This uses the credentials you created. We will input them into Streamlit Secrets later.
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # Load transactions and categories from the specific tabs
    transactions = conn.read(worksheet="transactions", ttl=0)
    categories_df = conn.read(worksheet="categories", ttl=0)
    return transactions, categories_df

# --- AUTHENTICATION SYSTEM ---
USERS = {
    "ethan": "petersen1",
    "alesa": "petersen2"
}

def login():
    st.title("🔐 Petersen Budget Login")
    user = st.text_input("Username").lower()
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if user in USERS and USERS[user] == password:
            st.session_state["authenticated"] = True
            st.session_state["user"] = user.capitalize()
            st.rerun()
        else:
            st.error("Invalid username or password")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login()
    st.stop()

# --- INITIALIZE DATA ---
df_transactions, df_cats = load_data()

# Helper to get category lists
def get_cat_list(type_filter):
    return df_cats[df_cats["Type"] == type_filter]["Name"].tolist()

# --- SIDEBAR: CATEGORY MANAGEMENT ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()
    
    st.divider()
    st.subheader("Manage Categories")
    cat_type = st.radio("Category Type", ["Income", "Expense"])
    new_cat_name = st.text_input(f"New {cat_type} Name")
    
    if st.button("Add Category"):
        if new_cat_name and new_cat_name not in get_cat_list(cat_type):
            new_row = pd.DataFrame([{"Type": cat_type, "Name": new_cat_name}])
            updated_cats = pd.concat([df_cats, new_row], ignore_index=True)
            conn.update(worksheet="categories", data=updated_cats)
            st.success(f"Added {new_cat_name}!")
            st.rerun()

# --- MAIN INTERFACE ---
st.title("📊 Petersen Family Budget")

tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    with st.form("transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_date = st.date_input("Date", datetime.now())
            t_type = st.selectbox("Type", ["Expense", "Income"])
        with col2:
            # Dynamically pull categories from the 'categories' tab
            current_cats = get_cat_list(t_type)
            t_cat = st.selectbox("Category", current_cats if current_cats else ["Default"])
            t_amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        submit = st.form_submit_button("Save to Google Sheets")
        
        if submit:
            new_entry = pd.DataFrame([{
                "Date": t_date.strftime('%Y-%m-%d'),
                "Type": t_type,
                "Category": t_cat,
                "Amount": t_amount,
                "User": st.session_state["user"]
            }])
            updated_df = pd.concat([df_transactions, new_entry], ignore_index=True)
            conn.update(worksheet="transactions", data=updated_df)
            st.success("Saved to your Spreadsheet!")
            st.rerun()

with tab2:
    st.subheader("Spending Analysis")
    if not df_transactions.empty:
        expenses_df = df_transactions[df_transactions["Type"] == "Expense"]
        if not expenses_df.empty:
            fig = px.pie(expenses_df, values="Amount", names="Category", title="Expenses by Category")
            st.plotly_chart(fig, use_container_width=True)
        
        # Summary Metrics
        income = df_transactions[df_transactions["Type"] == "Income"]["Amount"].sum()
        expense = df_transactions[df_transactions["Type"] == "Expense"]["Amount"].sum()
        st.metric("Monthly Balance", f"${(income - expense):,.2f}", delta=f"${income:,.2f} Income")
    else:
        st.info("No data found in Google Sheets yet.")

with tab3:
    st.subheader("Transaction History")
    if not df_transactions.empty:
        st.dataframe(df_transactions.sort_values(by="Date", ascending=False), use_container_width=True)
    else:
        st.write("Sheet is empty.")

