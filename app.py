import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Family Budget", page_icon="💰", layout="centered")

# CSS for Mobile Optimization & Actionable Rows
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 10px; border: 1px solid #e9ecef; }
    [data-testid="stMetricValue"] { font-size: 1.8rem; color: #007bff; }
    div[data-testid="stSidebarNav"] { display: none; }
    
    .delete-btn button { background-color: #ff4b4b !important; color: white !important; }
    .confirm-btn button { background-color: #dc3545 !important; color: white !important; font-weight: bold !important; }
    .update-btn button { background-color: #28a745 !important; color: white !important; }
    .select-btn button { height: 2.5em !important; background-color: #f0f2f6 !important; color: #31333F !important; border: 1px solid #dcdfe3 !important; padding: 0px !important; }
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
        try:
            t = conn.read(worksheet="transactions", ttl=0)
            if t.empty: t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        except:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        
        try:
            c = conn.read(worksheet="categories", ttl=0)
            if c.empty or "Name" not in c.columns:
                c = pd.DataFrame(columns=["Type", "Name"])
        except:
            c = pd.DataFrame(columns=["Type", "Name"])
            
        if not t.empty:
            t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
            t['Date'] = pd.to_datetime(t['Date'])
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
        income_total = df_transactions[df_transactions["Type"] == "Income"]["Amount"].sum()
        expense_total = df_transactions[df_transactions["Type"] == "Expense"]["Amount"].sum()
        balance = income_total - expense_total
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Income", f"${income_total:,.2f}")
        m2.metric("Expenses", f"${expense_total:,.2f}")
        m3.metric("Net Balance", f"${balance:,.2f}", delta=f"{balance:,.2f}")
        
        st.divider()
        col_ex, col_in = st.columns(2)
        with col_ex:
            st.write("### 💸 Expenses")
            expenses_df = df_transactions[df_transactions["Type"] == "Expense"]
            if not expenses_df.empty:
                fig_ex = px.pie(expenses_df, values="Amount", names="Category", hole=0.3)
                fig_ex.update_layout(showlegend=False)
                st.plotly_chart(fig_ex, use_container_width=True)

        with col_in:
            st.write("### 💰 Income")
            income_df = df_transactions[df_transactions["Type"] == "Income"]
            if not income_df.empty:
                fig_in = px.pie(income_df, values="Amount", names="Category", hole=0.3)
                fig_in.update_layout(showlegend=False)
                st.plotly_chart(fig_in, use_container_width=True)
    else:
        st.info("Start logging data to see your charts!")

with tab3:
    st.subheader("Transaction History")
    
    if not df_transactions.empty:
        # --- FILTER SECTION ---
        with st.expander("🔍 Search & Filter"):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                search_term = st.text_input("Search Category", "")
                date_range = st.date_input("Date Range", [datetime.now() - timedelta(days=30), datetime.now()])
            with f_col2:
                f_type = st.multiselect("Filter Type", ["Expense", "Income"], default=["Expense", "Income"])
        
        # Apply Filters
        df_filtered = df_transactions.copy()
        if search_term:
            df_filtered = df_filtered[df_filtered['Category'].str.contains(search_term, case=False)]
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            df_filtered = df_filtered[(df_filtered['Date'].dt.date >= start_date) & (df_filtered['Date'].dt.date <= end_date)]
        
        df_filtered = df_filtered[df_filtered['Type'].isin(f_type)]
        df_filtered = df_filtered.sort_values(by="Date", ascending=False)

        # --- LIST VIEW ---
        st.write(f"Showing {len(df_filtered)} transactions.")
        
        # Headers
        h1, h2, h3, h4 = st.columns([2, 2, 2, 1])
        h1.caption("**Date**")
        h2.caption("**Category**")
        h3.caption("**Amount**")
        h4.caption("**Action**")

        # Display rows
        for i, row in df_filtered.iterrows():
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            c1.write(row['Date'].strftime('%m/%d'))
            c2.write(row['Category'])
            c3.write(f"${row['Amount']:,.2f}")
            with c4:
                st.markdown('<div class="select-btn">', unsafe_allow_html=True)
                if st.button("Edit", key=f"edit_{i}"):
                    st.session_state["selected_index"] = i
                    st.session_state["delete_confirm"] = False
                st.markdown('</div>', unsafe_allow_html=True)

        # --- MANAGEMENT SECTION ---
        if "selected_index" in st.session_state:
            idx = st.session_state["selected_index"]
            if idx in df_transactions.index:
                target = df_transactions.loc[idx]
                st.markdown("---")
                st.subheader(f"🛠️ Managing {target['Category']}")
                
                m_del, m_edit = st.columns(2)
                
                with m_del:
                    if not st.session_state.get("delete_confirm", False):
                        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
                        if st.button("🗑️ Delete Transaction"):
                            st.session_state.delete_confirm = True
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                    else:
                        st.error("Delete this permanently?")
                        st.markdown('<div class="confirm-btn">', unsafe_allow_html=True)
                        if st.button("⚠️ CONFIRM DELETE"):
                            updated_df = df_transactions.drop(idx)
                            conn.update(worksheet="transactions", data=updated_df)
                            del st.session_state["selected_index"]
                            st.session_state.delete_confirm = False
                            st.success("Deleted!")
                            st.cache_resource.clear()
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                        if st.button("Cancel"):
                            st.session_state.delete_confirm = False
                            st.rerun()
                
                with m_edit:
                    with st.expander("✏️ Edit Details", expanded=True):
                        e_date = st.date_input("Edit Date", target["Date"])
                        e_cat = st.selectbox("Edit Category", get_cat_list(target["Type"]), index=get_cat_list(target["Type"]).index(target["Category"]) if target["Category"] in get_cat_list(target["Type"]) else 0)
                        e_amt = st.number_input("Edit Amount", value=float(target["Amount"]))
                        
                        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
                        if st.button("✅ Save Changes"):
                            df_transactions.at[idx, "Date"] = e_date.strftime('%Y-%m-%d')
                            df_transactions.at[idx, "Category"] = e_cat
                            df_transactions.at[idx, "Amount"] = e_amt
                            conn.update(worksheet="transactions", data=df_transactions)
                            del st.session_state["selected_index"]
                            st.success("Updated!")
                            st.cache_resource.clear()
                            st.rerun()
                        st.markdown('</div>', unsafe_allow_html=True)
                
                if st.button("Close Editor"):
                    del st.session_state["selected_index"]
                    st.rerun()
    else:
        st.info("History is currently empty.")

