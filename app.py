import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Tidy Mobile Rows & Persistent Alignment
st.markdown("""
    <style>
    .history-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 12px 5px;
        border-bottom: 1px solid #eee;
        width: 100%;
    }
    .h-date { width: 18%; font-size: 0.8rem; color: #888; }
    .h-cat  { width: 52%; font-size: 0.9rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .h-amt  { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; }

    /* Button Styling */
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Expander Styling */
    .stExpander { border-radius: 10px; border: 1px solid #f0f2f6; }
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENT AUTHENTICATION ---
USERS = {"ethan": "petersen1", "alesa": "petersen2"}

if "authenticated" not in st.session_state:
    params = st.query_params
    if "user" in params and params["user"] in USERS:
        st.session_state["authenticated"] = True
        st.session_state["user"] = params["user"].capitalize()
    else:
        st.session_state["authenticated"] = False

def login_screen():
    st.title("🔐 Petersen Budget")
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    rem = st.checkbox("Remember me", value=True)
    if st.button("Login"):
        if u in USERS and USERS[u] == p:
            st.session_state["authenticated"] = True
            st.session_state["user"] = u.capitalize()
            if rem: st.query_params["user"] = u
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state["authenticated"]:
    login_screen()
    st.stop()

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # We use ttl=0 to ensure we aren't seeing old data on refresh
        t = conn.read(worksheet="transactions", ttl=0)
        c = conn.read(worksheet="categories", ttl=0)
        
        if t is None or t.empty:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        if c is None or c.empty:
            c = pd.DataFrame(columns=["Type", "Name"])
        
        t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
        t['Date'] = pd.to_datetime(t['Date'], errors='coerce')
        t = t.dropna(subset=['Date'])
        return t, c
    except Exception:
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data()

def get_cat_list(t_filter):
    if df_c.empty: return []
    return df_c[df_c["Type"] == t_filter]["Name"].unique().tolist()

def get_smart_icon(cat_name, row_type):
    # Map icons based on category names
    name = cat_name.lower()
    if "grocer" in name: return "🛒"
    if "tithe" in name or "church" in name: return "⛪"
    if "fuel" in name or "gas" in name: return "⛽"
    if "rent" in name or "house" in name: return "🏠"
    if "ethan" in name or "alesa" in name: return "💰"
    if "salary" in name or "pay" in name: return "💵"
    # Fallback icons
    return "💸" if row_type == "Expense" else "💰"

# --- MAIN APP ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    t_type = st.radio("Is this an Income or Expense?", ["Expense", "Income"], horizontal=True)
    
    with st.form("add_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add one in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("Save to Google Sheets"):
            if f_clist:
                # CRITICAL FIX: Fresh read right before saving to prevent overwriting
                latest_ledger = conn.read(worksheet="transactions", ttl=0)
                if latest_ledger is None or latest_ledger.empty:
                    latest_ledger = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
                
                new_row = pd.DataFrame([{
                    "Date": f_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                
                # Append and Update
                updated_ledger = pd.concat([latest_ledger, new_row], ignore_index=True)
                conn.update(worksheet="transactions", data=updated_ledger)
                
                st.success(f"Successfully Recorded {f_cat}!")
                st.cache_resource.clear()
                st.rerun()
            else:
                st.error("Please add a category in the sidebar first!")

with tab2:
    if not df_t.empty:
        inc_sum = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp_sum = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Family Net Balance", f"${(inc_sum - exp_sum):,.2f}", delta=f"${inc_sum:,.2f} Income")
        st.divider()
        c_e, c_i = st.columns(2)
        with c_e:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c_i:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data yet.")

with tab3:
    st.subheader("Transaction Ledger")
    
    if not df_t.empty:
        # --- FILTERS ---
        with st.expander("🔍 Search & Filter"):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                search_cat = st.text_input("Search Category", "")
                date_range = st.date_input("Date Range", [datetime.now() - timedelta(days=30), datetime.now()])
            with f_col2:
                show_types = st.multiselect("Filter Type", ["Expense", "Income"], default=["Expense", "Income"])
        
        # Apply Filters
        work_df = df_t.copy()
        if search_cat:
            work_df = work_df[work_df['Category'].str.contains(search_cat, case=False)]
        if len(date_range) == 2:
            work_df = work_df[(work_df['Date'].dt.date >= date_range[0]) & (work_df['Date'].dt.date <= date_range[1])]
        work_df = work_df[work_df['Type'].isin(show_types)]
        
        # Newest on top
        work_df = work_df.sort_values(by="Date", ascending=False)
        
        # --- HEADER ---
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:52%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)

        # --- ROWS ---
        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            color = "#dc3545" if is_ex else "#28a745"
            prefix = "-" if is_ex else "+"
            icon = get_smart_icon(row['Category'], row['Type'])
            
            st.markdown(f"""
                <div class="history-row">
                    <div class="h-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="h-cat">{icon} {row['Category']}</div>
                    <div class="h-amt" style="color:{color};">{prefix}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("History is currently empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.header("Manage Categories")
    c_type = st.selectbox("Type", ["Expense", "Income"])
    c_new = st.text_input("New Category Name")
    if st.button("Add Category"):
        if c_new and c_new not in get_cat_list(c_type):
            updated_cats = pd.concat([df_c, pd.DataFrame([{"Type": c_type, "Name": c_new}])], ignore_index=True)
            conn.update(worksheet="categories", data=updated_cats)
            st.success(f"Added {c_new}!")
            st.cache_resource.clear()
            st.rerun()

