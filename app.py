import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Strict Horizontal Alignment & Mobile Polish
st.markdown("""
    <style>
    /* 1. CRITICAL: Prevent column stacking on mobile */
    [data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: space-between !important;
        gap: 0.2rem !important;
    }
    
    /* 2. Transaction Row Styling */
    .history-item {
        display: grid;
        grid-template-columns: 14% 48% 24% 14%;
        align-items: center;
        padding: 10px 0;
        border-bottom: 1px solid #f0f2f6;
        width: 100%;
    }
    
    .h-date { font-size: 0.75rem; color: #888; white-space: nowrap; }
    .h-cat  { font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .h-amt  { font-size: 0.85rem; font-weight: bold; text-align: right; }
    
    /* 3. Tiny Edit Button Fix */
    .stButton>button { 
        border-radius: 8px; 
        transition: 0.2s; 
    }
    
    .edit-btn-tiny button { 
        height: 1.8em !important; 
        width: 100% !important;
        min-width: 35px !important;
        padding: 0 !important; 
        font-size: 0.7rem !important;
        background-color: #f8f9fa !important;
        border: 1px solid #dee2e6 !important;
        color: #333 !important;
    }

    /* 4. General App UI */
    div[data-testid="stSidebarNav"] { display: none; }
    div[data-testid="stDialog"] { border-radius: 20px; }
    .delete-btn button { background-color: #ff4b4b !important; color: white !important; }
    .update-btn button { background-color: #28a745 !important; color: white !important; }
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
    st.error("Connection Failed. Check Secrets.")
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

# --- EDIT DIALOG ---
@st.dialog("Manage Entry")
def edit_dialog(idx, row):
    st.write(f"Editing: **{row['Category']}**")
    e_date = st.date_input("Date", row["Date"])
    clist = get_cat_list(row["Type"])
    e_cat = st.selectbox("Category", clist, index=clist.index(row["Category"]) if row["Category"] in clist else 0)
    e_amt = st.number_input("Amount ($)", value=float(row["Amount"]))
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
        if st.button("Save Changes"):
            df_t.at[idx, "Date"] = e_date.strftime('%Y-%m-%d')
            df_t.at[idx, "Category"] = e_cat
            df_t.at[idx, "Amount"] = e_amt
            conn.update(worksheet="transactions", data=df_t)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
        if st.button("Delete"):
            conn.update(worksheet="transactions", data=df_t.drop(idx))
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- MAIN INTERFACE ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add", "Visuals", "History"])

with tab1:
    t_type = st.radio("Entry Type", ["Expense", "Income"], horizontal=True)
    with st.form("add_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add one in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save to Sheets"):
            if f_clist:
                new_entry = pd.DataFrame([{"Date": f_date.strftime('%Y-%m-%d'), "Type": t_type, "Category": f_cat, "Amount": f_amt, "User": st.session_state["user"]}])
                conn.update(worksheet="transactions", data=pd.concat([df_t, new_entry], ignore_index=True))
                st.success("Entry Saved!")
                st.cache_resource.clear()
                st.rerun()

with tab2:
    if not df_t.empty:
        inc = df_t[df_t["Type"] == "Income"]["Amount"].sum()
        exp = df_t[df_t["Type"] == "Expense"]["Amount"].sum()
        st.metric("Family Net Balance", f"${(inc - exp):,.2f}", delta=f"${inc:,.2f} In")
        st.divider()
        c_ex, c_in = st.columns(2)
        with c_ex:
            dx = df_t[df_t["Type"] == "Expense"]
            if not dx.empty: st.plotly_chart(px.pie(dx, values="Amount", names="Category", title="Expenses"), use_container_width=True)
        with c_in:
            di = df_t[df_t["Type"] == "Income"]
            if not di.empty: st.plotly_chart(px.pie(di, values="Amount", names="Category", title="Income"), use_container_width=True)
    else:
        st.info("Log data to see charts.")

with tab3:
    if not df_t.empty:
        search = st.text_input("🔍 Search History", "")
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        if search: work_df = work_df[work_df['Category'].str.contains(search, case=False)]
        
        # Static Header
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #333; font-weight:bold; color:#555; font-size:0.7rem;">
                <div style="width:14%;">DATE</div>
                <div style="width:48%;">CATEGORY</div>
                <div style="width:24%; text-align:right;">AMOUNT</div>
                <div style="width:14%;"></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            clr = "#dc3545" if is_ex else "#28a745"
            sym = "-" if is_ex else "+"
            ico = "💸" if is_ex else "💰"
            
            # Using st.columns with specific weight to force horizontal alignment
            c1, c2, c3, c4 = st.columns([1.4, 4.8, 2.4, 1.4])
            with c1:
                st.markdown(f"<div class='h-date'>{row['Date'].strftime('%m/%d')}</div>", unsafe_allow_html=True)
            with c2:
                # Category name + Type icon
                st.markdown(f"<div class='h-cat'>{ico} {row['Category']}</div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div class='h-amt' style='color:{clr};'>{sym}${row['Amount']:,.0f}</div>", unsafe_allow_html=True)
            with c4:
                st.markdown('<div class="edit-btn-tiny">', unsafe_allow_html=True)
                if st.button("Edit", key=f"e_{i}"):
                    edit_dialog(i, row)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("No transaction history found.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.header("Manage Categories")
    cat_type = st.selectbox("Type", ["Expense", "Income"])
    cat_name = st.text_input("New Name")
    if st.button("Add Category"):
        if cat_name and cat_name not in get_cat_list(cat_type):
            conn.update(worksheet="categories", data=pd.concat([df_c, pd.DataFrame([{"Type": cat_type, "Name": cat_name}])], ignore_index=True))
            st.success(f"Added {cat_name}")
            st.cache_resource.clear()
            st.rerun()

