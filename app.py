import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURATION ---
st.set_page_config(page_title="Petersen Budget", page_icon="💰", layout="centered")

# CSS for Mobile Layout
st.markdown("""
    <style>
    [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 0.3rem !important; }
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
    .l-info { width: 52%; font-size: 0.85rem; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .l-amt { width: 30%; font-size: 0.9rem; font-weight: bold; text-align: right; flex-shrink: 0; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3em; }
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

def load_data_final():
    st.cache_data.clear()
    try:
        # 1. FORCE RANGE: Request A1:E2000 to break the 2-row cache limit
        t_df = conn.read(worksheet="transactions", spreadsheet="transactions!A1:E2000", ttl=0)
        c_df = conn.read(worksheet="categories", ttl=0)
        
        # 2. FILTER EMPTIES: Clean up the 1000+ empty rows we just forced
        if t_df is not None and not t_df.empty:
            # Clean Headers
            t_df.columns = [str(c).strip().title() for c in t_df.columns]
            
            # Ensure Key Columns Exist
            for col in ["Date", "Type", "Category", "Amount"]:
                if col not in t_df.columns:
                    t_df[col] = 0 if col == "Amount" else ""

            # Force Types
            t_df["Amount"] = pd.to_numeric(t_df["Amount"], errors='coerce').fillna(0)
            t_df['Date'] = pd.to_datetime(t_df['Date'], errors='coerce')
            
            # THE FIX: Drop rows where Date is NaT (Not a Time)
            # This removes the empty rows so the app doesn't crash
            t_df = t_df.dropna(subset=['Date'])
        else:
            t_df = pd.DataFrame(columns=["Date", "Type", "Category", "Amount", "User"])

        if c_df is not None and not c_df.empty:
            c_df.columns = [str(c).strip().title() for c in c_df.columns]
        else:
            c_df = pd.DataFrame(columns=["Type", "Name"])
            
        return t_df, c_df
    except Exception as e:
        # Sidebar warning instead of crash
        st.sidebar.error(f"Read Error: {e}")
        return pd.DataFrame(), pd.DataFrame()

# Load Data
df_t, df_c = load_data_final()

def get_cat_list(t_filter):
    if df_c is None or df_c.empty: return []
    col = "Name" if "Name" in df_c.columns else df_c.columns[1]
    return sorted(df_c[df_c["Type"] == t_filter][col].unique().tolist())

def get_icon(cat_name, row_type):
    n = str(cat_name).lower()
    if "groc" in n: return "🛒"
    if "tithe" in n or "church" in n: return "⛪"
    if "gas" in n or "fuel" in n: return "⛽"
    if "ethan" in n: return "👤"
    if "alesa" in n: return "👩"
    return "💸" if row_type == "Expense" else "💰"

# --- UI ---
st.title("📊 Petersen Budget")
tab1, tab2, tab3 = st.tabs(["Add", "Visuals", "History"])

with tab1:
    t_type = st.radio("Type", ["Expense", "Income"], horizontal=True)
    with st.form("entry_form", clear_on_submit=True):
        f_date = st.date_input("Date", datetime.now())
        f_clist = get_cat_list(t_type)
        f_cat = st.selectbox("Category", f_clist if f_clist else ["(Add categories in sidebar)"])
        f_amt = st.number_input("Amount ($)", min_value=0.0, step=0.01)
        if st.form_submit_button("Save"):
            # Load fresh to append safely
            latest_t, _ = load_data_final()
            new_row = pd.DataFrame([{
                "Date": f_date.strftime('%Y-%m-%d'),
                "Type": t_type,
                "Category": f_cat,
                "Amount": float(f_amt),
                "User": st.session_state["user"]
            }])
            updated = pd.concat([latest_t, new_row], ignore_index=True)
            conn.update(worksheet="transactions", data=updated)
            st.success("Saved!")
            time.sleep(1)
            st.rerun()

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
    st.subheader("Ledger")
    if not df_t.empty:
        work_df = df_t.copy().sort_values(by="Date", ascending=False)
        st.markdown('<div style="display:flex; justify-content:space-between; font-weight:bold; font-size:0.7rem; color:grey; border-bottom:1px solid #333;"><div>DATE</div><div>CATEGORY</div><div style="text-align:right;">AMOUNT</div></div>', unsafe_allow_html=True)
        
        for i, row in work_df.iterrows():
            # UI SAFETY CHECK: Ensure we have a valid date to display
            if pd.isnull(row['Date']): continue
            
            try:
                d_str = row['Date'].strftime('%m/%d')
            except:
                continue # Skip row if date is broken

            is_ex = str(row['Type']).capitalize() == 'Expense'
            color = "#dc3545" if is_ex else "#28a745"
            icon = get_icon(row['Category'], row['Type'])
            
            st.markdown(f"""
                <div class="ledger-row">
                    <div class="l-date">{d_str}</div>
                    <div class="l-info">{icon} {row['Category']}</div>
                    <div class="l-amt" style="color:{color};">{"-" if is_ex else "+"}${row['Amount']:,.0f}</div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("History is empty.")

# --- SIDEBAR ---
with st.sidebar:
    st.title(f"Hi, {st.session_state['user']}!")
    if st.button("🔄 FORCE SYNC"):
        st.cache_data.clear()
        st.rerun()
    
    # DEBUG VIEW: Check this to see row count!
    with st.expander("Debug Info"):
        st.write(f"Rows Loaded: {len(df_t)}")
        st.dataframe(df_t)
        
    if st.button("Logout"):
        st.session_state["authenticated"] = False
        st.rerun()
    st.divider()
    st.header("Categories")
    ct = st.selectbox("Type", ["Expense", "Income"])
    cn = st.text_input("Name")
    if st.button("Add"):
        if cn:
            _, latest_c = load_data_final()
            updated_c = pd.concat([latest_c, pd.DataFrame([{"Type": ct, "Name": cn}])], ignore_index=True)
            conn.update(worksheet="categories", data=updated_c)
            st.rerun()


