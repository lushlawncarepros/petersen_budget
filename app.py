import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for a Stable Mobile Ledger
st.markdown("""
    <style>
    /* Force rows to be horizontal and fit the screen width */
    .ledger-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 10px 5px;
        border-bottom: 1px solid #eee;
        width: 100%;
        gap: 10px;
    }
    .l-date { width: 15%; font-size: 0.75rem; color: #888; flex-shrink: 0; }
    .l-cat  { width: 55%; font-size: 0.9rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .l-amt  { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; flex-shrink: 0; }

    /* Button & Input Styling */
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
    div[data-testid="stSidebarNav"] { display: none; }
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

# --- DATA ENGINE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # ttl=0 is vital: it tells the app "Don't remember the past, look at the sheet NOW"
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

def get_icon(cat_name, row_type):
    name = cat_name.lower()
    if "groc" in name: return "🛒"
    if "tith" in name or "church" in name: return "⛪"
    if "gas" in name or "fuel" in name: return "⛽"
    if "ethan" in name or "alesa" in name: return "💰"
    return "💸" if row_type == "Expense" else "💵"

# --- MAIN APP ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("New Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Go to Sidebar to add categories)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        
        if st.form_submit_button("Save Entry"):
            if f_clist:
                # 1. READ FRESH: Get the most current ledger from the cloud
                fresh_ledger = conn.read(worksheet="transactions", ttl=0)
                if fresh_ledger is None:
                    fresh_ledger = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
                
                # 2. CREATE: Build the new transaction
                new_entry = pd.DataFrame([{
                    "Date": f_date.strftime('%Y-%m-%d'),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                
                # 3. APPEND: Add it to the list
                final_ledger = pd.concat([fresh_ledger, new_entry], ignore_index=True)
                
                # 4. SAVE: Push the whole updated list back
                conn.update(worksheet="transactions", data=final_ledger)
                
                st.success(f"Saved {f_cat} transaction!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    if not df_t.empty:
        inc_total = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp_total = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Balance", f"${(inc_total - exp_total):,.2f}", delta=f"${inc_total:,.2f} Income")
        st.divider()
        col_ex, col_in = st.columns(2)
        with col_ex:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with col_in:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data yet.")

with tab3:
    st.subheader("Transaction History")
    
    if not df_t.empty:
        # --- FILTERS ---
        with st.expander("🔍 Search & Filter History"):
            c1, c2 = st.columns(2)
            with c1:
                s_cat = st.text_input("Search Category", "")
                s_date = st.date_input("Date Range", [datetime.now() - timedelta(days=30), datetime.now()])
            with c2:
                s_types = st.multiselect("Show Types", ["Expense", "Income"], default=["Expense", "Income"])
        
        # Apply Filters
        work_df = df_t.copy()
        if s_cat:
            work_df = work_df[work_df['Category'].str.contains(s_cat, case=False)]
        if len(s_date) == 2:
            work_df = work_df[(work_df['Date'].dt.date >= s_date[0]) & (work_df['Date'].dt.date <= s_date[1])]
        work_df = work_df[work_df['Type'].isin(s_types)]
        
        # Newest at Top
        work_df = work_df.sort_values(by="Date", ascending=False)
        
        # --- HEADER ---
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:18%;">DATE</div>
                <div style="width:52%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)

        # --- DATA ROWS ---
        for i, row in work_df.iterrows():
            is_exp = row['Type'] == 'Expense'
            clr = "#dc3545" if is_exp else "#28a745"
            sym = "-" if is_exp else "+"
            ico = get_icon(row['Category'], row['Type'])
            
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="l-cat">{row['Category']} {ico}</div>
                    <div class="l-amt" style="color:{clr};">{sym}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Ledger is currently empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.header("Manage Categories")
    new_type = st.selectbox("Category Type", ["Expense", "Income"])
    new_name = st.text_input("Category Name")
    if st.button("Add Category"):
        if new_name and new_name not in get_cat_list(new_type):
            conn.update(worksheet="categories", data=pd.concat([df_c, pd.DataFrame([{"Type": new_type, "Name": new_name}])], ignore_index=True))
            st.success(f"Added {new_name}")
            st.cache_resource.clear()
            st.rerun()

