import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Strict Mobile Rows (Tidy & Non-Stacking)
st.markdown("""
    <style>
    .ledger-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 12px 5px;
        border-bottom: 1px solid #f0f2f6;
        width: 100%;
    }
    .l-date { width: 18%; font-size: 0.8rem; color: #888; flex-shrink: 0; }
    .l-cat  { width: 52%; font-size: 0.9rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .l-amt  { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; flex-shrink: 0; }

    /* Button Styling */
    .stButton>button { width: 100%; border-radius: 12px; height: 3.2em; transition: 0.2s; }
    div[data-testid="stSidebarNav"] { display: none; }
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

# --- DATA CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # Using ttl=0 to minimize caching
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
    return sorted(df_c[df_c["Type"] == t_filter]["Name"].unique().tolist())

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tithe" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    if "salary" in n or "pay" in n: return "💵"
    return "💸" if row_type == "Expense" else "💰"

# --- MAIN APP ---
st.title("📊 Petersen Family Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("New Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("Save to Google Sheets"):
            if f_clist:
                # MANDATORY: Clear cache before reading to ensure we append to the REAL latest version
                st.cache_data.clear()
                
                # Read fresh from cloud
                latest_ledger = conn.read(worksheet="transactions", ttl=0)
                if latest_ledger is None: latest_ledger = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
                
                # Build new entry
                new_entry = pd.DataFrame([{
                    "Date": f_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                
                # Append and Save
                updated_ledger = pd.concat([latest_ledger, new_entry], ignore_index=True)
                conn.update(worksheet="transactions", data=updated_ledger)
                
                st.success(f"Saved {f_cat} Entry!")
                st.cache_data.clear()
                st.rerun()

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} Total Income")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c2:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data logged yet.")

with tab3:
    st.subheader("Transaction History")
    st.caption("Showing all recorded transactions (no filters).")
    
    if not df_t.empty:
        # Force newest to top
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        
        # Header
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:52%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            clr = "#dc3545" if is_ex else "#28a745"
            sym = "-" if is_ex else "+"
            ico = get_icon(row['Category'], row['Type'])
            
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="l-cat">{row['Category']} {ico}</div>
                    <div class="l-amt" style="color:{clr};">{sym}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("History is currently empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    
    # NEW: Manual Sync Button to fix the "Stale Data" glitch
    if st.button("🔄 Sync with Google Sheets"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
        
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
        
    st.divider()
    st.header("Manage Categories")
    c_type = st.selectbox("Type", ["Expense", "Income"])
    c_name = st.text_input("New Category Name")
    if st.button("Add Category"):
        if c_name and c_name not in get_cat_list(c_type):
            latest_cats = conn.read(worksheet="categories", ttl=0)
            new_cat = pd.DataFrame([{"Type": c_type, "Name": c_name}])
            updated_cats = pd.concat([latest_cats, new_cat], ignore_index=True)
            conn.update(worksheet="categories", data=updated_cats)
            st.success(f"Added {c_name}!")
            st.cache_data.clear()
            st.rerun()

