import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# Basic CSS for clean mobile rows
st.markdown("""
    <style>
    /* Simple horizontal row that fits the screen */
    .history-row {
        display: flex;
        flex-direction: row;
        justify-content: space-between;
        align-items: center;
        padding: 12px 5px;
        border-bottom: 1px solid #eee;
        width: 100%;
        font-family: sans-serif;
    }
    .h-date { width: 15%; font-size: 0.8rem; color: #888; }
    .h-cat  { width: 55%; font-size: 0.9rem; font-weight: 500; }
    .h-amt  { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; }

    /* Buttons & UI */
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; }
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

# --- GOOGLE SHEETS CONNECTION ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception:
    st.error("Connection Failed.")
    st.stop()

def load_data():
    try:
        t = conn.read(worksheet="transactions", ttl=0)
        c = conn.read(worksheet="categories", ttl=0)
        if t.empty: t = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])
        if c.empty: c = pd.DataFrame(columns=["Type", "Name"])
        
        t["Amount"] = pd.to_numeric(t["Amount"], errors='coerce').fillna(0)
        t['Date'] = pd.to_datetime(t['Date'], errors='coerce')
        t = t.dropna(subset=['Date'])
        return t, c
    except:
        return pd.DataFrame(), pd.DataFrame()

df_t, df_c = load_data()

def get_cat_list(t_filter):
    if df_c.empty: return []
    return df_c[df_c["Type"] == t_filter]["Name"].unique().tolist()

# --- MAIN APP ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add", "Visuals", "History"])

with tab1:
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add one in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save to Sheets"):
            if f_clist:
                new_row = pd.DataFrame([{"Date": f_date.strftime('%Y-%m-%d'), "Type": t_type, "Category": f_cat, "Amount": f_amt, "User": st.session_state["user"]}])
                conn.update(worksheet="transactions", data=pd.concat([df_t, new_row], ignore_index=True))
                st.success("Saved!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} In")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c2:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("Log some data first!")

with tab3:
    if not df_t.empty:
        # Sort and filter
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        
        # Simple Header
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding-bottom:5px; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.75rem;">
                <div style="width:15%;">DATE</div>
                <div style="width:55%;">CATEGORY</div>
                <div style="width:30%; text-align:right;">AMOUNT</div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            clr = "#dc3545" if is_ex else "#28a745"
            sym = "-" if is_ex else "+"
            ico = "💸" if is_ex else "💰"
            
            # Very basic horizontal row using HTML Flexbox
            st.markdown(f"""
                <div class="history-row">
                    <div class="h-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="h-cat">{ico} {row['Category']}</div>
                    <div class="h-amt" style="color:{clr};">{sym}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No history yet.")

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
    c_name = st.text_input("New Category Name")
    if st.button("Add Category"):
        if c_name and c_name not in get_cat_list(c_type):
            conn.update(worksheet="categories", data=pd.concat([df_c, pd.DataFrame([{"Type": c_type, "Name": c_name}])], ignore_index=True))
            st.success(f"Added {c_name}")
            st.cache_resource.clear()
            st.rerun()

