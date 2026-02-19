import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS: Custom HTML List with Invisible Click Overlay
st.markdown("""
    <style>
    /* Hide Sidebar Nav */
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* 1. VISUAL CARD STYLING */
    .trans-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background-color: white;
        border-bottom: 1px solid #f0f2f6;
        padding: 12px 5px; /* Vertical padding breathes, horizontal keeps it aligned */
        height: 55px;
        font-family: "Source Sans Pro", sans-serif;
    }
    
    /* Column Spacing */
    .tr-date { width: 15%; font-size: 0.75rem; color: #999; font-weight: 500; }
    .tr-cat  { width: 55%; font-size: 0.9rem; color: #333; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding-right: 10px; }
    .tr-amt  { width: 30%; font-size: 0.95rem; font-weight: 700; text-align: right; }
    
    /* 2. INVISIBLE BUTTON OVERLAY */
    /* This button sits exactly on top of the visual card but is invisible */
    .row-overlay button {
        background-color: transparent !important;
        color: transparent !important;
        border: none !important;
        width: 100%;
        height: 55px; /* Must match .trans-row height */
        margin-top: -55px; /* Pulls it up to cover the row */
        z-index: 2;
        cursor: pointer;
    }
    
    .row-overlay button:hover {
        background-color: rgba(0,0,0,0.02) !important; /* Slight hover effect */
        color: transparent !important;
    }
    
    /* Global Button Polish */
    .stButton>button { border-radius: 10px; }
    
    /* Header */
    .hist-header {
        display: flex;
        justify-content: space-between;
        padding: 0 5px 5px 5px;
        border-bottom: 2px solid #eee;
        margin-bottom: 5px;
        color: #888;
        font-size: 0.7rem;
        font-weight: bold;
    }
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

if not st.session_state["authenticated"]:
    st.title("🔐 Login")
    u = st.text_input("Username").lower()
    p = st.text_input("Password", type="password")
    if st.button("Login"):
        if u in USERS and USERS[u] == p:
            st.session_state["authenticated"] = True
            st.session_state["user"] = u.capitalize()
            st.query_params["user"] = u
            st.rerun()
    st.stop()

# --- DATA ENGINE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data_safe():
    st.cache_data.clear()
    try:
        t_df = conn.read(worksheet="transactions", ttl=0, dtype=str)
        c_df = conn.read(worksheet="categories", ttl=0, dtype=str)
        
        if t_df is not None and not t_df.empty:
            t_df.columns = [str(c).strip().title() for c in t_df.columns]
            for col in ["Date", "Type", "Category", "Amount", "User"]:
                if col not in t_df.columns: t_df[col] = ""

            t_df["Amount"] = t_df["Amount"].astype(str).str.replace(r'[$,]', '', regex=True)
            t_df["Amount"] = pd.to_numeric(t_df["Amount"], errors='coerce').fillna(0)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date'])
            t_df = t_df.reset_index(drop=True)
        else:
            t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])

        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
        else:
            c_df = pd.DataFrame(columns=["Type", "Name"])
            
        return t_df, c_df
    except Exception:
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

df_t, df_c = load_data_safe()

def get_cat_list(t_filter):
    if df_c.empty or "Name" not in df_c.columns: return []
    cats = df_c[df_c["Type"] == t_filter]["Name"].unique().tolist()
    return sorted(cats, key=str.lower)

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tithe" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    return "💸" if row_type == "Expense" else "💰"

# --- EDITOR DIALOG ---
@st.dialog("Manage Entry")
def edit_dialog(row_index, row_data):
    st.write(f"Editing: **{row_data['Category']}**")
    e_date = st.date_input("Date", row_data["Date"])
    clist = get_cat_list(row_data["Type"])
    # Safe index lookup
    try:
        c_idx = clist.index(row_data["Category"])
    except ValueError:
        c_idx = 0
        
    e_cat = st.selectbox("Category", clist, index=c_idx)
    e_amt = st.number_input("Amount ($)", value=float(row_data["Amount"]))
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Update", use_container_width=True):
            df_t.at[row_index, "Date"] = pd.to_datetime(e_date)
            df_t.at[row_index, "Category"] = e_cat
            df_t.at[row_index, "Amount"] = e_amt
            df_t['Date'] = df_t['Date'].dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=df_t)
            st.success("Updated!")
            time.sleep(0.5)
            st.rerun()
    with c2:
        if st.button("🗑️ Delete", use_container_width=True):
            new_df = df_t.drop(row_index)
            new_df['Date'] = new_df['Date'].dt.strftime('%Y-%m-%d')
            conn.update(worksheet="transactions", data=new_df)
            st.success("Deleted!")
            time.sleep(0.5)
            st.rerun()

# --- APP ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save"):
            if f_clist:
                latest_t, _ = load_data_safe()
                new_entry = pd.DataFrame([{
                    "Date": pd.to_datetime(f_date),
                    "Type": t_type,
                    "Category": f_cat,
                    "Amount": float(f_amt),
                    "User": st.session_state["user"]
                }])
                updated = pd.concat([latest_t, new_entry], ignore_index=True)
                updated['Date'] = updated['Date'].dt.strftime('%Y-%m-%d')
                conn.update(worksheet="transactions", data=updated)
                st.success(f"Saved {f_cat}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Please add a category first!")

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} In")
        c1, c2 = st.columns(2)
        with c1:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c2:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("No data yet.")

with tab3:
    if not df_t.empty:
        work_df = df_t.copy()
        work_df['sort_date'] = pd.to_datetime(work_df['Date'])
        work_df = work_df.sort_values(by="sort_date", ascending=False)
        
        # Header
        st.markdown("""
        <div class="hist-header">
            <div style="width:20%">DATE</div>
            <div style="width:50%">CATEGORY</div>
            <div style="width:30%; text-align:right">PRICE</div>
        </div>
        """, unsafe_allow_html=True)
        
        for i, row in work_df.iterrows():
            if pd.isnull(row['Date']): continue
            
            # Format Data
            d_str = row['Date'].strftime('%m/%d')
            is_ex = row['Type'] == 'Expense'
            
            # Icons and Styling
            icon = get_icon(row['Category'], row['Type'])
            prefix = "-" if is_ex else "+"
            color = "#d32f2f" if is_ex else "#2e7d32" # Red or Green
            
            # 1. VISUAL CARD (HTML)
            st.markdown(f"""
                <div class="trans-row">
                    <div class="tr-date">{d_str}</div>
                    <div class="tr-cat">{icon} {row['Category']}</div>
                    <div class="tr-amt" style="color:{color};">{prefix}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
            
            # 2. CLICK TARGET (Button)
            st.markdown('<div class="row-overlay">', unsafe_allow_html=True)
            if st.button(f"btn_{i}", key=f"h_{i}", label_visibility="hidden"):
                edit_dialog(i, row)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("History is empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("🔄 Force Sync"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()
    
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()
    
    st.divider()
    st.header("Categories")
    with st.form("cat_form", clear_on_submit=True):
        ct = st.selectbox("Type", ["Expense", "Income"])
        cn = st.text_input("Name")
        if st.form_submit_button("Add Category"):
            if cn:
                st.cache_resource.clear()
                _, latest_c = load_data_safe()
                updated_c = pd.concat([latest_c, pd.DataFrame([{"Type": ct, "Name": cn}])], ignore_index=True)
                conn.update(worksheet="categories", data=updated_c)
                st.success("Added!")
                time.sleep(0.5)
                st.rerun()


