import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for a Strict, Tidy Mobile Ledger
st.markdown("""
    <style>
    /* Force horizontal rows even on narrow mobile screens */
    .ledger-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 12px 5px;
        border-bottom: 1px solid #f0f2f6;
        width: 100%;
        gap: 8px;
    }
    .l-date { width: 18%; font-size: 0.75rem; color: #888; flex-shrink: 0; }
    .l-cat  { width: 52%; font-size: 0.85rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .l-amt  { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; flex-shrink: 0; }

    /* Button & Input Styling */
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; transition: 0.2s; }
    div[data-testid="stSidebarNav"] { display: none; }
    .stMultiSelect div[role="listbox"] { border-radius: 10px; }
    
    /* Make the metric labels look better on mobile */
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
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
    rem = st.checkbox("Remember me on this device", value=True)
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

# --- DATA CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # ttl=0 ensures we don't look at old data
        t = conn.read(worksheet="transactions", ttl=0)
        c = conn.read(worksheet="categories", ttl=0)
        
        # Build empty dataframes if the sheets are fresh/missing
        if t is None or t.empty:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        if c is None or c.empty:
            c = pd.DataFrame(columns=["Type", "Name"])
        
        # Ensure correct data types for math and dates
        t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
        t['Date'] = pd.to_datetime(t['Date'], errors='coerce')
        t = t.dropna(subset=['Date'])
        return t, c
    except Exception:
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data()

def get_cat_list(t_filter):
    if df_c.empty: return []
    return sorted(df_c[df_c["Type"] == t_filter]["Name"].unique().tolist())

def get_smart_icon(cat_name, row_type):
    n = cat_name.lower()
    if "groc" in n: return "🛒"
    if "tith" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n or "alesa" in n: return "👤"
    if "salary" in n or "pay" in n: return "💵"
    if "rent" in n or "mortgage" in n: return "🏠"
    return "💸" if row_type == "Expense" else "💰"

# --- MAIN APP ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("New Transaction")
    t_type = st.radio("Is this an Income or Expense?", ["Expense", "Income"], horizontal=True)
    
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("Save to Google Sheets"):
            if f_clist:
                # 1. LIVE READ: Get current sheet state before appending
                latest_ledger = conn.read(worksheet="transactions", ttl=0)
                if latest_ledger is None: latest_ledger = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
                
                # 2. APPEND: Add new row to the end
                new_entry = pd.DataFrame([{
                    "Date": f_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                
                # 3. OVERWRITE GOOGLE SHEET with the full updated list
                updated_ledger = pd.concat([latest_ledger, new_entry], ignore_index=True)
                conn.update(worksheet="transactions", data=updated_ledger)
                
                st.success(f"Added {f_cat} for ${f_amt:,.2f}!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Family Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} Income")
        st.divider()
        c_ex, c_in = st.columns(2)
        with c_ex:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c_in:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data yet. Start by adding a transaction!")

with tab3:
    st.subheader("Transaction History")
    
    if not df_t.empty:
        # --- TOGGLE FILTERS ---
        with st.expander("🔍 Filter History", expanded=True):
            f1, f2 = st.columns(2)
            with f1:
                # Toggle Categories (Radial-style multiselect)
                all_recorded_cats = sorted(df_t["Category"].unique().tolist())
                sel_cats = st.multiselect("Toggle Categories", options=all_recorded_cats, default=all_recorded_cats)
                
                s_range = st.date_input("Date Range", [datetime.now() - timedelta(days=30), datetime.now()])
            with f2:
                # Toggle Expense/Income
                sel_types = st.multiselect("Show Types", ["Expense", "Income"], default=["Expense", "Income"])
        
        # Apply Filters
        work_df = df_t.copy()
        if sel_cats:
            work_df = work_df[work_df['Category'].isin(sel_cats)]
        if len(s_range) == 2:
            work_df = work_df[(work_df['Date'].dt.date >= s_range[0]) & (work_df['Date'].dt.date <= s_range[1])]
        if sel_types:
            work_df = work_df[work_df['Type'].isin(sel_types)]
        
        # Sort so newest is always first
        work_df = work_df.sort_values(by="Date", ascending=False)
        
        # --- LEDGER HEADER ---
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:52%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)

        # --- DATA ROWS ---
        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            clr = "#dc3545" if is_ex else "#28a745"
            sym = "-" if is_ex else "+"
            ico = get_smart_icon(row['Category'], row['Type'])
            
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="l-cat">{ico} {row['Category']}</div>
                    <div class="l-amt" style="color:{clr};">{sym}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("The history is empty. Try adding an entry!")

# --- SIDEBAR: CATEGORY SETUP ---
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

