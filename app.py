import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Aggressive Mobile Layout & No-Stack Rows
st.markdown("""
    <style>
    /* GLOBAL MOBILE OVERRIDES */
    [data-testid="column"] {
        min-width: 0px !important;
        flex: 1 1 auto !important;
    }
    
    /* FORCE Horizontal Flex for History Rows */
    .t-row {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
        padding: 8px 0;
        border-bottom: 1px solid #f0f2f6;
    }
    
    .t-date { width: 14%; font-size: 0.7rem; color: #888; flex-shrink: 0; }
    .t-info { width: 50%; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-grow: 1; padding: 0 5px; }
    .t-amt  { width: 24%; text-align: right; font-weight: bold; font-size: 0.85rem; flex-shrink: 0; }
    .t-edit { width: 12%; text-align: right; flex-shrink: 0; }

    /* Ultra-Compact Button */
    .edit-btn-tiny button { 
        height: 1.8em !important; 
        width: 1.8em !important; 
        min-width: 1.8em !important;
        padding: 0 !important;
        font-size: 0.8rem !important;
        background-color: #f0f2f6 !important;
        border: 1px solid #dcdfe3 !important;
        border-radius: 6px !important;
    }
    
    /* General Button Polish */
    .stButton>button { border-radius: 8px; }
    div[data-testid="stSidebarNav"] { display: none; }
    
    /* Dialog Polish */
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

# --- EDIT DIALOG ---
@st.dialog("Manage Entry")
def edit_dialog(idx, row):
    st.write(f"Editing: **{row['Category']}**")
    e_date = st.date_input("Date", row["Date"])
    clist = get_cat_list(row["Type"])
    e_cat = st.selectbox("Category", clist, index=clist.index(row["Category"]) if row["Category"] in clist else 0)
    e_amt = st.number_input("Amount ($)", value=float(row["Amount"]))
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="update-btn">', unsafe_allow_html=True)
        if st.button("Save"):
            df_t.at[idx, "Date"] = e_date.strftime('%Y-%m-%d')
            df_t.at[idx, "Category"] = e_cat
            df_t.at[idx, "Amount"] = e_amt
            conn.update(worksheet="transactions", data=df_t)
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="delete-btn">', unsafe_allow_html=True)
        if st.button("Delete"):
            conn.update(worksheet="transactions", data=df_t.drop(idx))
            st.cache_resource.clear()
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- APP ---
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
                new_row = pd.DataFrame([{"Date": f_date.strftime('%Y-%m-%d'), "Type": t_type, "Category": f_cat, "Amount": f_amt, "User": st.session_state["user"]}])
                conn.update(worksheet="transactions", data=pd.concat([df_t, new_row], ignore_index=True))
                st.success("Entry Saved!")
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
        st.info("No data yet.")

with tab3:
    if not df_t.empty:
        search = st.text_input("🔍 Search", "")
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        if search: work_df = work_df[work_df['Category'].str.contains(search, case=False)]
        
        # Header (Now strictly forced horizontal)
        st.markdown("""
            <div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:2px solid #eee; font-weight:bold; color:grey; font-size:0.65rem;">
                <div style="width:14%;">DATE</div>
                <div style="width:50%;">CAT / TYPE</div>
                <div style="width:24%; text-align:right;">AMOUNT</div>
                <div style="width:12%;"></div>
            </div>
        """, unsafe_allow_html=True)

        for i, row in work_df.iterrows():
            is_ex = row['Type'] == 'Expense'
            color = "#dc3545" if is_ex else "#28a745"
            prefix = "-" if is_ex else "+"
            icon = "💸" if is_ex else "💰"
            
            # Using custom HTML for the row to prevent ANY stacking
            # We then place the Streamlit button in the last slot
            st.markdown(f"""
                <div class="t-row">
                    <div class="t-date">{row['Date'].strftime('%m/%d')}</div>
                    <div class="t-info">{icon} {row['Category']}</div>
                    <div class="t-amt" style="color:{color};">{prefix}${row['Amount']:,.0f}</div>
                    <div class="t-edit"></div>
                </div>
            """, unsafe_allow_html=True)
            
            # Use negative margin trick to put the real button on top of the HTML placeholder
            _, _, _, btn_col = st.columns([14, 50, 24, 12])
            with btn_col:
                st.markdown('<div class="edit-btn-tiny" style="margin-top:-40px;">', unsafe_allow_html=True)
                if st.button("📝", key=f"e_{i}"):
                    edit_dialog(i, row)
                st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("History is empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    st.divider()
    st.subheader("Manage Categories")
    c_type = st.selectbox("Type", ["Expense", "Income"])
    c_new = st.text_input("Name")
    if st.button("Add Category"):
        if c_new and c_new not in get_cat_list(c_type):
            conn.update(worksheet="categories", data=pd.concat([df_c, pd.DataFrame([{"Type": c_type, "Name": c_new}])], ignore_index=True))
            st.success(f"Added {c_new}")
            st.cache_resource.clear()
            st.rerun()

