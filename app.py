import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
import random
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
    .l-date { width: 18%; font-size: 0.75rem; color: #888; }
    .l-cat  { width: 52%; font-size: 0.9rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .l-amt  { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; }
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

# --- DATA ENGINE ---
conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    # Clear cache to force fresh fetch
    st.cache_data.clear()
    
    # We use a trick to bypass caching by adding a random number to the query
    cb = random.randint(1, 1000000)
    
    try:
        # PULL TRANSACTIONS
        # We use the standard read but try to force the range to be massive
        t_df = conn.read(worksheet="transactions", ttl=0, usecols=[0,1,2,3,4])
        
        if t_df is not None and not t_df.empty:
            t_df.columns = [str(c).strip().title() for c in t_df.columns]
            t_df["Amount"] = pd.to_numeric(t_df["Amount"], errors='coerce').fillna(0)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            t_df = t_df.dropna(subset=['Date'])
        else:
            t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])

        # PULL CATEGORIES
        c_df = conn.read(worksheet="categories", ttl=0)
        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
        else:
            c_df = pd.DataFrame(columns=["Type", "Name"])
            
        return t_df, c_df
    except Exception as e:
        st.error(f"Connection error: {e}")
        return pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"]), pd.DataFrame(columns=["Type", "Name"])

# Fetch
df_t, df_c = get_data()

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
    if "salary" in n or "pay" in n: return "💵"
    return "💸" if row_type == "Expense" else "💰"

# --- MAIN APP ---
st.title("📊 Petersen Family Budget")
tab1, tab2, tab3 = st.tabs(["Add Entry", "Visuals", "History"])

with tab1:
    st.subheader("Add Transaction")
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save Entry"):
            # FRESH READ
            latest_t, _ = get_data()
            new_entry = pd.DataFrame([{
                "Date": f_date.strftime('%Y-%m-%d'),
                "Type": t_type,
                "Category": f_cat,
                "Amount": float(f_amt),
                "User": st.session_state["user"]
            }])
            # Append & Push
            updated = pd.concat([latest_t, new_entry], ignore_index=True)
            conn.update(worksheet="transactions", data=updated)
            st.success("Entry Saved!")
            st.cache_data.clear()
            st.rerun()

with tab2:
    if not df_t.empty and "Type" in df_t.columns:
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
        st.info("No data found in history.")

with tab3:
    st.subheader("Ledger")
    if not df_t.empty:
        # Final Sort
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
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
                    <div class="l-cat">{get_icon(row['Category'], row['Type'])} {row['Category']}</div>
                    <div class="l-amt" style="color:{color};">{"-" if is_ex else "+"}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.write("No transactions recorded yet.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    
    # MANUAL OVERRIDE SYNC
    if st.button("🔄 HARD SYNC"):
        st.cache_data.clear()
        st.rerun()

    with st.expander("🛠️ Debug (Check Rows)"):
        st.write(f"Transactions: {len(df_t)}")
        st.write("Headers:", list(df_t.columns))
        st.dataframe(df_t)

    if st.button("Log Out"):
        st.session_state["authenticated"] = False
        st.query_params.clear()
        st.rerun()
    
    st.divider()
    st.header("Categories")
    ct = st.selectbox("Type", ["Expense", "Income"])
    cn = st.text_input("Name")
    if st.button("Add"):
        if cn:
            _, latest_c = get_data()
            updated_c = pd.concat([latest_c, pd.DataFrame([{"Type": ct, "Name": cn}])], ignore_index=True)
            conn.update(worksheet="categories", data=updated_c)
            st.success("Added!")
            st.cache_data.clear()
            st.rerun()

