import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS: Implementing "Grok's" Mobile UI Tweaks & Ethan's Horizontal Row Lock
st.markdown("""
    <style>
    /* Force columns to stay side-by-side on S25/Narrow screens */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        gap: 0.3rem !important;
    }
    [data-testid="column"] {
        min-width: 0px !important;
        flex: 1 1 auto !important;
    }

    /* History Row Styles */
    .ledger-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid #f0f2f6;
        width: 100%;
    }
    .l-date { width: 18%; font-size: 0.75rem; color: #888; flex-shrink: 0; }
    /* Grok's Ellipsis Fix for long categories */
    .l-info { 
        width: 52%; 
        font-size: 0.85rem; 
        font-weight: 500; 
        overflow: hidden; 
        text-overflow: ellipsis; 
        white-space: nowrap; 
    }
    .l-amt { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; flex-shrink: 0; }

    /* Button Styling */
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; transition: 0.2s; }
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Dialog/Form Polish */
    div[data-testid="stDialog"] { border-radius: 20px; }
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
    st.title("🔐 Petersen Family Budget")
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u in USERS and USERS[u] == p:
            st.session_state["authenticated"] = True
            st.session_state["user"] = u.capitalize()
            st.query_params["user"] = u
            st.rerun()
        else:
            st.error("Invalid credentials")

if not st.session_state["authenticated"]:
    login_screen()
    st.stop()

# --- DATA ENGINE (Implementing Grok's Fixes) ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data_sql():
    st.cache_data.clear() # Clear cache to ensure fresh read
    try:
        # 1. Primary: SQL Bypass (Often ignores row-limits)
        t_df = conn.query('SELECT * FROM "transactions"', ttl=0)
    except Exception as e:
        st.sidebar.warning(f"SQL Read failed: {e}. Trying explicit range read...")
        # 2. Fallback: Explicit full read with nrows=None as suggested by Grok
        t_df = conn.read(worksheet="transactions", ttl=0, nrows=None, usecols=[0,1,2,3,4])
    
    # 3. Reading Categories
    try:
        c_df = conn.read(worksheet="categories", ttl=0)
    except:
        c_df = pd.DataFrame(columns=["Type", "Name"])

    # 4. Cleaning Logic
    if t_df is not None and not t_df.empty:
        t_df.columns = [str(c).strip().title() for c in t_df.columns]
        if "Amount" in t_df.columns:
            t_df["Amount"] = pd.to_numeric(t_df["Amount"], errors='coerce').fillna(0)
        if "Date" in t_df.columns:
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date'])
    else:
        t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])

    if c_df is not None and not c_df.empty:
        c_df.columns = [str(c).strip().title() for c in c_df.columns]
    
    return t_df, c_df

# Global State
df_t, df_c = load_data_sql()

def get_cat_list(t_filter):
    if df_c is None or df_c.empty: return []
    # Support both "Name" or index-based column identification
    col = "Name" if "Name" in df_c.columns else df_c.columns[1]
    return sorted(df_c[df_c["Type"] == t_filter][col].unique().tolist())

def get_smart_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tith" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    if "salary" in n or "pay" in n: return "💵"
    return "💸" if row_type == "Expense" else "💰"

# --- MAIN APP ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("New Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        # Grok's Enhanced Save Logic
        if st.form_submit_button("Save to Google Sheets"):
            if f_clist:
                # 1. Fresh pull of the full sheet state
                latest_t, _ = load_data_sql()
                # 2. Build new row
                new_entry = pd.DataFrame([{
                    "Date": f_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                # 3. Append to history (prevents overwriting)
                updated = pd.concat([latest_t, new_entry], ignore_index=True)
                # 4. Push to Sheets
                conn.update(worksheet="transactions", data=updated)
                
                # Success Feedback with row count to confirm it worked
                st.success(f"Saved! New total records: {len(updated)}")
                time.sleep(1)
                st.rerun()

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Family Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} Income")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c2:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data yet. Log something to see visuals.")

with tab3:
    st.subheader("Transaction Ledger")
    if not df_t.empty:
        # Newest at the top
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        
        # Custom Header
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:52%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in work_df.iterrows():
            is_ex = str(row['Type']).capitalize() == 'Expense'
            color = "#dc3545" if is_ex else "#28a745"
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="l-info">{get_smart_icon(row['Category'], row['Type'])} {row['Category']}</div>
                    <div class="l-amt" style="color:{color};">{"-" if is_ex else "+"}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("History is currently empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    
    # Debug Info Expander
    with st.expander("🛠️ Debug Connection"):
        st.write(f"Rows found in App: {len(df_t)}")
        st.write("Current Headers:", list(df_t.columns))
        if st.button("Force Hard Re-Sync"):
            st.cache_data.clear()
            st.rerun()

    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    
    st.divider()
    st.header("Manage Categories")
    c_type = st.selectbox("Type", ["Expense", "Income"])
    c_name = st.text_input("New Name")
    if st.button("Add Category"):
        if c_name:
            _, latest_c = load_data_sql()
            new_cat = pd.DataFrame([{"Type": c_type, "Name": c_name}])
            updated_c = pd.concat([latest_c, new_cat], ignore_index=True)
            conn.update(worksheet="categories", data=updated_c)
            st.success(f"Added {c_name}!")
            st.rerun()

