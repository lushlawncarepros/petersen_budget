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
    div[data-testid="stSidebarNav"] { display: none; }
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
@st.cache_resource(ttl=60)
def get_connection():
    try:
        return st.connection("gsheets", type=GSheetsConnection)
    except Exception as e:
        st.error(f"⚠️ Connection Setup Error: {e}")
        return None

conn = get_connection()

def load_data():
    if not conn: return pd.DataFrame(), pd.DataFrame()
    try:
        # Load transactions
        try:
            t = conn.read(worksheet="transactions", ttl=0)
            if t.empty: t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        except:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        
        # Load categories
        try:
            c = conn.read(worksheet="categories", ttl=0)
            if c.empty or "Name" not in c.columns:
                c = pd.DataFrame(columns=["Type", "Name"])
        except:
            c = pd.DataFrame(columns=["Type", "Name"])
            
        # Ensure numeric
        if not t.empty:
            t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
        return t, c
    except Exception as e:
        st.error(f"❌ Data Loading Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_transactions, df_cats = load_data()

def get_cat_list(type_filter):
    if df_cats.empty: return []
    return df_cats[df_cats["Type"] == type_filter]["Name"].unique().tolist()

# --- SIDEBAR: CATEGORY MANAGEMENT ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()
    
    st.divider()
    st.header("⚙️ App Settings")
    st.subheader("Manage Categories")
    manage_type = st.selectbox("Type to Manage", ["Expense", "Income"])
    new_cat_name = st.text_input(f"New {manage_type} Name")
    
    if st.button("Add Category"):
        if new_cat_name:
            if new_cat_name not in get_cat_list(manage_type):
                new_row = pd.DataFrame([{"Type": manage_type, "Name": new_cat_name}])
                updated_cats = pd.concat([df_cats, new_row], ignore_index=True)
                conn.update(worksheet="categories", data=updated_cats)
                st.success(f"Added {new_cat_name}!")
                st.cache_resource.clear()
                st.rerun()
            else:
                st.warning("That category already exists!")

# --- MAIN INTERFACE ---
st.title("📊 Petersen Family Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add New Transaction")
    t_type = st.radio("Is this an Income or Expense?", ["Expense", "Income"], horizontal=True)
    
    with st.form("transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            t_date = st.date_input("Date", datetime.now())
            t_amount = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        with col2:
            current_cats = get_cat_list(t_type)
            t_cat = st.selectbox("Category", current_cats if current_cats else ["(Add categories in sidebar)"])
        
        if st.form_submit_button("Save to Google Sheets"):
            if not current_cats:
                st.error("Please add a category in the sidebar first!")
            else:
                new_entry = pd.DataFrame([{
                    "Date": t_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": t_cat,
                    "Amount": t_amount,
                    "User": st.session_state["user"]
                }])
                updated_df = pd.concat([df_transactions, new_entry], ignore_index=True)
                conn.update(worksheet="transactions", data=updated_df)
                st.success(f"Successfully saved {t_cat}!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    st.subheader("Income vs. Expenses")
    if not df_transactions.empty:
        # High-level Metrics
        income_total = df_transactions[df_transactions["Type"] == "Income"]["Amount"].sum()
        expense_total = df_transactions[df_transactions["Type"] == "Expense"]["Amount"].sum()
        balance = income_total - expense_total
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Income", f"${income_total:,.2f}")
        m2.metric("Total Expenses", f"${expense_total:,.2f}")
        m3.metric("Net Balance", f"${balance:,.2f}", delta=f"{balance:,.2f}")
        
        st.divider()
        
        # Dual Charts
        col_ex, col_in = st.columns(2)
        
        with col_ex:
            st.write("### 💸 Expenses")
            expenses_df = df_transactions[df_transactions["Type"] == "Expense"]
            if not expenses_df.empty:
                fig_ex = px.pie(expenses_df, values="Amount", names="Category", hole=0.3)
                fig_ex.update_layout(showlegend=False) # Keep clean on mobile
                st.plotly_chart(fig_ex, use_container_width=True)
            else:
                st.info("No expense data.")

        with col_in:
            st.write("### 💰 Income")
            income_df = df_transactions[df_transactions["Type"] == "Income"]
            if not income_df.empty:
                fig_in = px.pie(income_df, values="Amount", names="Category", hole=0.3)
                fig_in.update_layout(showlegend=False)
                st.plotly_chart(fig_in, use_container_width=True)
            else:
                st.info("No income data.")
    else:
        st.info("Start logging data to see your charts!")

with tab3:
    st.subheader("Transaction History")
    if not df_transactions.empty:
        st.dataframe(df_transactions.sort_values(by="Date", ascending=False), use_container_width=True)
    else:
        st.write("No transactions found yet.")

