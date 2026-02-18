import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Strict Mobile Rows
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
    .stButton>button { width: 100%; border-radius: 12px; height: 3.2em; }
    div[data-testid="stSidebarNav"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# --- AUTHENTICATION ---
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

# --- DATA CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # 1. READ TRANSACTIONS
        t_raw = conn.read(worksheet="transactions", ttl=0)
        if t_raw is None or t_raw.empty:
            t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        else:
            t = t_raw.copy()
            # Clean up column names (strip spaces, lowercase) for internal matching
            t.columns = [str(c).strip().capitalize() for c in t.columns]
            
        # 2. READ CATEGORIES
        c_raw = conn.read(worksheet="categories", ttl=0)
        if c_raw is None or c_raw.empty:
            c = pd.DataFrame(columns=["Type", "Name"])
        else:
            c = c_raw.copy()
            c.columns = [str(c).strip().capitalize() for c in c.columns]
        
        # 3. DATA CLEANING
        if "Amount" in t.columns:
            t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
        if "Date" in t.columns:
            t['Date'] = pd.to_datetime(t['Date'], errors='coerce')
            t = t.dropna(subset=['Date'])
            
        return t, c
    except Exception as e:
        st.sidebar.error(f"Read Error: {e}")
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data()

def get_cat_list(t_filter):
    if df_c.empty or "Name" not in df_c.columns: return []
    return sorted(df_c[df_c["Type"] == t_filter]["Name"].unique().tolist())

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tith" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    return "💸" if row_type == "Expense" else "💰"

# --- MAIN INTERFACE ---
st.title("📊 Petersen Family Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add one in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save to Google Sheets"):
            # FRESH READ TO PREVENT OVERWRITE
            st.cache_data.clear()
            latest_t, _ = load_data()
            new_entry = pd.DataFrame([{
                "Date": f_date.strftime('%Y-%m-%d'),
                "Type": t_type,
                "Category": f_cat,
                "Amount": float(f_amt),
                "User": st.session_state["user"]
            }])
            updated = pd.concat([latest_t, new_entry], ignore_index=True)
            conn.update(worksheet="transactions", data=updated)
            st.success("Entry Saved!")
            st.cache_data.clear()
            st.rerun()

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} Income")
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
    if not df_t.empty:
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:52%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)
        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            color = "#dc3545" if is_ex else "#28a745"
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="l-cat">{get_icon(row['Category'], row['Type'])} {row['Category']}</div>
                    <div class="l-amt" style="color:{color};">{"-" if is_ex else "+"}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("History is currently empty.")

# --- SIDEBAR: DEBUG & CATEGORIES ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    
    # DEBUG SECTION
    with st.expander("🛠️ Debug Info"):
        st.write(f"Total Transactions Found: {len(df_t)}")
        st.write("Columns Found:", list(df_t.columns))
        if st.button("Force Total Reset"):
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
    c_name = st.text_input("New Name")
    if st.button("Add Category"):
        if c_name:
            _, latest_c = load_data()
            new_cat = pd.DataFrame([{"Type": c_type, "Name": c_name}])
            updated_c = pd.concat([latest_c, new_cat], ignore_index=True)
            conn.update(worksheet="categories", data=updated_c)
            st.success(f"Added {c_name}!")
            st.cache_data.clear()
            st.rerun()

