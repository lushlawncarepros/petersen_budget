import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Family Budget", page_icon="💰", layout="centered")

# CSS for Mobile Optimization
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #007bff; color: white; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION ---
USERS = {"ethan": "petersen1", "alesa": "petersen2"}

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

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
            st.error("Invalid credentials")

if not st.session_state["authenticated"]:
    login()
    st.stop()

# --- GOOGLE SHEETS CONNECTION ---
@st.cache_resource(ttl=600)
def get_connection():
    try:
        # Simplified connection call
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"⚠️ Connection Setup Error: {e}")
        return None

conn = get_connection()

def load_data():
    if not conn: return pd.DataFrame(), pd.DataFrame()
    try:
        # Load transactions and categories
        t = conn.read(worksheet="transactions", ttl=0)
        c = conn.read(worksheet="categories", ttl=0)
        # Ensure numeric columns are actually numbers
        if not t.empty:
            t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
        return t, c
    except Exception as e:
        st.error(f"❌ Sheet Loading Error: {e}")
        st.info("Check your Sheet tabs: 'transactions' and 'categories'.")
        return pd.DataFrame(), pd.DataFrame()

df_transactions, df_cats = load_data()

def get_cat_list(type_filter):
    if df_cats.empty: return []
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
            current_cats = get_cat_list(t_type)
            t_cat = st.selectbox("Category", current_cats if current_cats else ["Default"])
            t_amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("Save to Google Sheets"):
            new_entry = pd.DataFrame([{
                "Date": t_date.strftime('%Y-%m-%d'),
                "Type": t_type,
                "Category": t_cat,
                "Amount": t_amount,
                "User": st.session_state["user"]
            }])
            updated_df = pd.concat([df_transactions, new_entry], ignore_index=True)
            conn.update(worksheet="transactions", data=updated_df)
            st.success("Saved!")
            st.rerun()

with tab2:
    st.subheader("Spending Analysis")
    if not df_transactions.empty:
        expenses_df = df_transactions[df_transactions["Type"] == "Expense"]
        if not expenses_df.empty:
            fig = px.pie(expenses_df, values="Amount", names="Category")
            st.plotly_chart(fig, use_container_width=True)
        
        income = df_transactions[df_transactions["Type"] == "Income"]["Amount"].sum()
        expense = df_transactions[df_transactions["Type"] == "Expense"]["Amount"].sum()
        st.metric("Monthly Balance", f"${(income - expense):,.2f}", delta=f"${income:,.2f} Income")
    else:
        st.info("No data found yet.")

with tab3:
    st.subheader("Transaction History")
    if not df_transactions.empty:
        st.dataframe(df_transactions.sort_values(by="Date", ascending=False), use_container_width=True)

